"""What the screen sends: touches, values and keyboard text."""

import logging

from librescreen import state as g
from librescreen.config import settings
from librescreen.pages import connections
from librescreen.printer import heating
from librescreen.screen import pageids as ids
from librescreen.screen import navigation
from librescreen.screen.navigation import page_to, send_ui_version, request_language
from librescreen.util.cpp import b2s, cstr, to_string

log = logging.getLogger(__name__)


def parse_cmd_msg_from_tjc_screen(cmd):
    """``cmd`` is the 4096 byte read buffer (zero padded) of the main loop."""
    g.screen.event_id = cmd[0]
    log.debug("#########################%s", b2s(cstr(cmd)))
    log.info("0x%x", cmd[0])
    log.info("0x%x", cmd[1])
    log.info("0x%x", cmd[2])
    log.info("0x%x", cmd[3])
    event_id = g.screen.event_id
    if event_id in (0x65, 0x70, 0x71, 0x86, 0x87, 0x88, 0x89):
        g.port.forget()         # a touch, a typed value or a power-up: the screen may show something else now
    if event_id == 0x03:
        pass        # error while reading the screen firmware data, screen recovery mode
    elif event_id == 0x05:
        g.update.get_0x05 = True
        log.debug("Ready to send data")
        log.info("0x%x", cmd[0])
        # receiving 0x05 means the screen data can be sent
    elif event_id == 0x1a:
        log.debug("Invalid variable name")
    elif event_id == navigation.LANGUAGE_FRAME:
        g.config.language_status = cmd[1]        # the screen owns the language (``lang``, kept in its EEPROM)
        log.info("Screen language: %d", cmd[1])
    elif event_id == 0x24:
        g.update.get_0x24 = True
    elif event_id == 0x65:
        g.screen.page_id = cmd[1]
        g.screen.widget_id = cmd[2]
        g.screen.type_id = cmd[3]
        if cmd[1] != g.screen.page:             # a click of a page that is not the one expected: ask which page the screen shows
            navigation.ask_page()
        from librescreen import clicks
        clicks.handle(g.screen.page_id, g.screen.widget_id, g.screen.type_id)
    elif event_id == 0x66:
        navigation.page_reported(cmd[1])        # the answer to sendme: the page the screen shows
    elif event_id in (0x67, 0x68):
        pass
    elif event_id == 0x70:
        log.info("0x%x", event_id)
        tjc_event_keyboard(cmd)
    elif event_id == 0x71:
        g.screen.page_id = cmd[1]
        tjc_event_setted_handler(cmd[1], cmd[2], cmd[3], cmd[4])
    elif event_id in (0x86, 0x87, 0x88, 0x89):
        log.info("0x%x", event_id)
        if event_id == 0x88:        # the screen has just powered up: it knows nothing of what the host sent before
            send_ui_version()
            request_language()
            if g.screen.page != ids.LOGO:
                page_to(g.screen.page)
    elif event_id == 0x91:
        g.screen.page = ids.LOGO
        page_to(ids.UPDATE_SUCCESS)
    elif event_id == 0xfd:
        g.update.get_0xfd = True
        log.info("0x%x 0x%x 0x%x 0x%x ", cmd[0], cmd[1], cmd[2], cmd[3])
    elif event_id == 0xfe:
        g.update.get_0xfe = True
        log.info("0x%x 0x%x 0x%x 0x%x ", cmd[0], cmd[1], cmd[2], cmd[3])
    elif event_id == 0xff:
        log.info("0x%x", event_id)
    elif event_id == 0x04:
        g.update.get_0x04 = True
        log.info("0x%x", cmd[0])
    elif event_id == 0x06:
        g.update.get_0x06 = True


def _printing_target(action, widget, limit, store=None, prefix=""):
    """Value of a printing page widget: clamp, apply, echo it back to the widget (``prefix`` is the "/ " of a target) and store it."""
    def handle(number):
        g.screen.printing_keyboard_enabled = False
        number = min(number, limit)
        action(number)
        if widget:
            g.port.txt(widget, prefix + to_string(number))
        if store:
            store(number)
    return handle


def _filament_target(action, limit, store=None, reopen=True):
    """Value of a filament page widget: clamp and apply, then redraw the page."""
    def handle(number):
        number = min(number, limit)
        action(number)
        if store:
            store(number)
        if reopen:
            page_to(ids.MAIN if g.screen.temperature_from_main else ids.FILAMENT)
        g.screen.temperature_from_main = False
    return handle


# (page, widget) -> handler(number).  NOTE: the keyboard (keybdB) always reports page 20 for the speed and flow
# values, they live on the second printing page (printing_2.n2 / n3)
SETTED = {
    (ids.PRINTING, ids.PRINTING_EXTRUDER): _printing_target(
        lambda n: heating.set_extruder_target(n), "nozzle_set", 350, lambda n: settings.set_extruder_target(n), "/ "),
    (ids.PRINTING, ids.PRINTING_HEATER_BED): _printing_target(
        lambda n: heating.set_heater_bed_target(n), "bed_set", 120, lambda n: settings.set_heater_bed_target(n), "/ "),
    (ids.PRINTING, ids.PRINTING_FAN_1): _printing_target(lambda n: heating.set_fan0(n), None, 100),
    (ids.PRINTING, ids.PRINTING_FAN_2): _printing_target(lambda n: heating.set_fan2(n), None, 100),      # 4.4.2 CLL fan2 added
    (ids.PRINTING, ids.PRINTING_FAN_3): _printing_target(lambda n: heating.set_fan3(n), None, 100),
    (ids.PRINTING, ids.PRINTING_2_SPEED): _printing_target(lambda n: heating.set_printer_speed(n), "speed_val", 150),
    (ids.PRINTING, ids.PRINTING_2_FLOW): _printing_target(lambda n: heating.set_printer_flow(n), "flow_val", 150),
    (ids.PRINTING, ids.PRINTING_HOT): _printing_target(
        lambda n: heating.set_hot_target(n), None, 60, lambda n: settings.set_hot_target(n)),
    (ids.FILAMENT, ids.FILAMENT_SET_EXTRUDER): _filament_target(
        lambda n: heating.set_extruder_target(n), 350, lambda n: settings.set_extruder_target(n)),
    (ids.FILAMENT, ids.FILAMENT_SET_HEATERBED): _filament_target(
        lambda n: heating.set_heater_bed_target(n), 120, lambda n: settings.set_heater_bed_target(n)),
    (ids.FILAMENT, ids.FILAMENT_SET_FAN_1): _filament_target(lambda n: heating.set_fan0(n), 100),
    (ids.FILAMENT, ids.FILAMENT_SET_FAN_2): _filament_target(lambda n: heating.set_fan2(n), 100),
    (ids.FILAMENT, ids.FILAMENT_SET_FAN_3): _filament_target(lambda n: heating.set_fan3(n), 100),
    (ids.FILAMENT, ids.FILAMENT_SET_HOT): _filament_target(
        lambda n: heating.set_hot_target(n), 60, lambda n: settings.set_hot_target(n)),
}


def tjc_event_setted_handler(page_id, widget_id, first, second):
    log.debug("!!!%s", page_id)
    log.debug("!!!%s", widget_id)
    log.debug("!!!%s", chr(first))
    log.debug("!!!%s", chr(second))
    handler = SETTED.get((page_id, widget_id))
    if handler:
        handler((second << 8) + first)


def tjc_event_keyboard(cmd):
    pass
    log.info("Keyboard value received, mode %d, row %d\n", cmd[1], cmd[2])        # the text may be a password
    psk = cstr(cmd[3:])         # char *psk = &cmd[3];
    # display_firmware: the keyboard page sends its mode (cmd[1]), see netui.py
    mode = connections.KB_PSK_SCANNED if cmd[1] == ids.WIFI_LIST else cmd[1]      # the stock keyboard sends the page id
    if mode in (connections.KB_PSK_SCANNED, connections.KB_PSK_SAVED, connections.KB_HIDDEN_SSID, connections.KB_HIDDEN_PSK):
        connections.keyboard_text(mode, b2s(psk))
