"""Start-up sequence and main loop of the screen backend ("xindi")."""

import argparse
import faulthandler
import fcntl
import logging
import os
import queue
import signal
import sys
import time

from xindi import state as g
from xindi.config import runtime, settings
from xindi.moonraker.rpc_messages import json_parse
from xindi.moonraker.ws_client import MoonrakerClient
from xindi.pages import refresh
from xindi.printer import klipper
from xindi.screen import events, flash, navigation, pageids as ids, rx
from xindi.screen.transfer import sent_jpg_thread_handle
from xindi.system.network import (get_ssid_list_pages,
                                  get_wlan0_status,
                                  mks_wifi_hdlevent_thread,
                                  mks_wpa_scan_scanresults)
from xindi.util.guard import run_guarded
from xindi.util.cpp import pthread_create, terminate

log = logging.getLogger(__name__)

REFRESH_INTERVAL = 0.05     # s between two redraws of the page


def connect_moonraker():
    url = runtime.cfg.websocket_url()
    log.info("%s", url)

    g.ep = MoonrakerClient(runtime.cfg.moonraker_host, runtime.cfg.moonraker_port)
    log.debug("%s", g.ep.url())
    log.debug("%s", g.ep.poll_status())
    log.debug("%s", int(g.ep.connected()))

    connected_count = 0
    while not g.ep.connected():
        log.debug("%sNot connected: %s", connected_count, int(g.ep.connected()))
        g.ep.close()
        g.ep.connect(url)
        connected_count += 1
        time.sleep(1)
        g.ep.poll_status()
        time.sleep(1)


def reconnect_moonraker(url, wait=5.0):
    """The websocket to Moonraker is gone (Moonraker was restarted, the network blinked): connects again and asks for the state of the printer.
    Returns True when it did; False when the connection is open (nothing to do) or could not be made yet."""
    status = g.ep.poll_status()
    if status in ("Open", "Connecting"):
        return False
    log.info("The connection to Moonraker is %s, connecting again", status)
    g.ep.close()
    g.ep.connect(url)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(0.2)
        if g.ep.poll_status() == "Open":
            log.info("Connected to Moonraker again")
            klipper.sub_object_status()
            klipper.get_object_status()
            return True
    return False


def keep_moonraker_connected(url):
    """The thread that keeps the connection to Moonraker (the connection is made once at the start and ends with whatever ends Moonraker)."""
    while True:
        time.sleep(1)
        try:
            reconnect_moonraker(url)
        except Exception:
            log.exception("Connecting to Moonraker again failed")


def open_screen_port():
    """Open the screen's serial port; returns its file descriptor or -1."""
    if not g.port.open():
        print("Open tty failed")
        return -1
    log.debug("%d", g.port.fd)
    print("Open tty success")
    return g.port.fd


def start_screen(fd, frames):
    """Start reading the screen, load the printer state and show the first page."""
    try:
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NDELAY)

        # the port is read by a thread of its own, the frames wait in a queue (see screen_rx.py): the main loop
        # spends its time on writing to the screen and may be busy for a while without losing what the screen
        # sent meanwhile
        parser = rx.FrameParser()
        pthread_create(lambda _: rx.reader_thread(fd, parser, frames), None)

        settings.get_total_time()
        time.sleep(2)
        klipper.sub_object_status()       # subscribe to the printer objects

        time.sleep(2)

        klipper.get_object_status()       # query the required values
        time.sleep(2)
        get_wlan0_status()
        mks_wpa_scan_scanresults()
        get_ssid_list_pages()
        time.sleep(3)

        # CLL UI / SOC version check of the main page (the screen may start later: see ui.send_ui_version)
        navigation.send_ui_version()
        navigation.request_language()
        g.screen.previous_page = ids.LOGO
        g.screen.page = ids.OPEN_LANGUAGE if settings.get_oobe_enabled() else ids.MAIN
        navigation.page_to(g.screen.page)
    except Exception as e:
        log.error("Page main error, %s", str(e))


def main_loop(frames):
    next_refresh = 0.0
    next_page_check = 0.0
    while True:
        frame = rx.next_frame(frames, max(0.0, next_refresh - time.monotonic()))
        if frame is not None:
            run_guarded(events.parse_cmd_msg_from_tjc_screen, frame.ljust(4096, b"\0"))
        if time.monotonic() >= next_refresh:
            run_guarded(refresh.show)
            next_refresh = time.monotonic() + REFRESH_INTERVAL
        if time.monotonic() >= next_page_check:
            if not g.pictures.send_jpg_status:          # not while the pictures of the list are sent
                navigation.ask_page()
            next_page_check = time.monotonic() + navigation.PAGE_CHECK_INTERVAL


def main():
    pthread_create(mks_wifi_hdlevent_thread, None)
    connect_moonraker()
    pthread_create(json_parse, None)
    pthread_create(lambda _: keep_moonraker_connected(g.ep.url()), None)
    pthread_create(sent_jpg_thread_handle, None)        # preview picture thread

    frames = queue.Queue()
    fd = open_screen_port()
    if fd >= 0:
        start_screen(fd, frames)
    main_loop(frames)


def setup_logging():
    """Log to stdout (the journal of the service); ``[log] level = debug`` (or XINDI_LOG=debug) shows the chatty messages too."""
    level = os.environ.get("XINDI_LOG", runtime.cfg.log_level).upper()
    logging.basicConfig(stream=sys.stdout, level=getattr(logging, level, logging.INFO),
                        format="%(levelname).1s %(name)s: %(message)s")


def print_state(signum=None, frame=None):
    """kill -USR2 <pid>: what the service believes (the page, the state of the printer, the flags of the pages), for a service that does not do what it should."""
    flags = {name: value for name, value in vars(g.screen).items() if isinstance(value, bool) and value}
    print("STATE page=%s print_stats=%r idle_timeout=%r webhooks=%r moonraker=%s flags=%s" % (
        g.screen.page, g.klippy.print_stats_state, g.klippy.idle_timeout_state, g.klippy.webhooks_state, g.ep.status if g.ep else None,
        sorted(flags)), flush=True)


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="xindi", description="Backend of the TJC screen of the QIDI Q1 Pro for Klipper and Moonraker.")
    parser.add_argument("host", nargs="?", help="Moonraker host (overrides the configuration file; default localhost)")
    parser.add_argument("-c", "--config", metavar="FILE", help="configuration file (default: $XINDI_CONFIG, ~/.config/xindi/xindi.ini, /etc/xindi/xindi.ini)")
    parser.add_argument("--flash-screen", metavar="FILE.tft", help="download the screen firmware FILE.tft into the screen and exit (stop the service first)")
    return parser.parse_args(argv[1:])


def run():
    args = parse_args(sys.argv)
    runtime.load(args.config, args.host)
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    setup_logging()
    if args.flash_screen:
        if not os.path.isfile(args.flash_screen):
            print("xindi: %s is not a file" % args.flash_screen, file=sys.stderr)
            return 2
        return flash.main(args.flash_screen)
    try:
        faulthandler.register(signal.SIGUSR1, all_threads=True)       # kill -USR1 <pid> prints what every thread is doing (a stuck service)
        signal.signal(signal.SIGUSR2, print_state)
    except (AttributeError, ValueError, OSError):
        pass
    try:
        return main()
    except KeyboardInterrupt:
        return 130
    except SystemExit:
        raise
    except BaseException as e:      # uncaught exception -> std::terminate()
        terminate(e)
