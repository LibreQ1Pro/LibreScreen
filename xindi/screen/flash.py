"""Download a .tft into the screen with the service stopped.

The screen receives ``whmi-wri <size>,<baud>,0`` at its current baud rate,
then acknowledges at the transfer baud rate. Each block of at most 4096
bytes needs a 0x05 acknowledgement, including the last block.
"""

import os
import select
import signal
import stat
import sys
import termios
import time

from xindi.config import runtime
from xindi.screen.serial import cfmakeraw_zeroed


BLOCK_SIZE = 4096
WRITE_SIZE = 2048
IO_TIMEOUT = 10.0
ACK_TIMEOUT = 10.0


def _baud_speed(baud):
    speed = getattr(termios, "B%d" % baud, None)
    if baud <= 0 or speed is None:
        raise ValueError("unsupported baud rate: %s" % baud)
    return speed


def _set_baud(fd, baud):
    iflag, oflag, cflag, lflag, cc = cfmakeraw_zeroed()
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 0
    speed = _baud_speed(baud)
    termios.tcflush(fd, termios.TCIOFLUSH)
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag | termios.CREAD, lflag, speed, speed, cc])


def _open_port(port, baud):
    fd = os.open(port, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY)
    try:
        _set_baud(fd, baud)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _wait_ready(fd, reading, deadline, operation):
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out %s" % operation)
        try:
            readable, writable, _ = select.select([fd] if reading else [], [] if reading else [fd], [], remaining)
        except InterruptedError:
            continue
        if readable or writable:
            return


def _drain_timeout(signum, frame):
    raise TimeoutError("timed out draining the screen UART")


def _drain(fd, deadline):
    # Flashing runs on the CLI's main thread. An alarm bounds the real
    # tcdrain(), preserving its UART semantics rather than polling TIOCOUTQ.
    started = time.monotonic()
    remaining = deadline - started
    if remaining <= 0:
        raise TimeoutError("timed out draining the screen UART")
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    previous_handler = signal.signal(signal.SIGALRM, _drain_timeout)
    try:
        signal.setitimer(signal.ITIMER_REAL, remaining)
        while True:
            try:
                termios.tcdrain(fd)
                return
            except InterruptedError:
                continue
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            remaining = max(0.000001, previous_timer[0] - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])


def _write_all(fd, data, timeout):
    deadline = time.monotonic() + timeout
    for start in range(0, len(data), WRITE_SIZE):
        chunk = data[start:start + WRITE_SIZE]
        offset = 0
        while offset < len(chunk):
            _wait_ready(fd, False, deadline, "writing to the screen")
            try:
                written = os.write(fd, chunk[offset:])
            except (BlockingIOError, InterruptedError):
                continue
            if written <= 0:
                raise OSError("serial write returned no data")
            offset += written
        # The hardware-tested sender drains each full 2048-byte piece;
        # a short tail is followed by the screen's block ACK instead.
        if len(chunk) == WRITE_SIZE:
            _drain(fd, deadline)


def _wait_ack(fd, operation, timeout=ACK_TIMEOUT):
    deadline = time.monotonic() + timeout
    while True:
        _wait_ready(fd, True, deadline, operation)
        try:
            data = os.read(fd, 1)
        except (BlockingIOError, InterruptedError):
            continue
        if not data:
            raise OSError("serial port closed while %s" % operation)
        if data == b"\x05":
            return


def main(tft_file):
    """Return 0 after the final ACK, 1 on transfer failure, 2 on bad input, 130 on interruption."""
    cfg = runtime.cfg
    fd = None
    confirmed = 0
    try:
        try:
            _baud_speed(cfg.screen_baud)
            _baud_speed(cfg.transfer_baud)
            with open(tft_file, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError("firmware is not a regular file")
                data = source.read()
            if not data:
                raise ValueError("firmware file is empty")
        except (OSError, ValueError) as e:
            print("xindi: invalid screen firmware or configuration: %s" % e, file=sys.stderr)
            return 2

        print("Screen firmware: %s (%d bytes)" % (tft_file, len(data)), flush=True)
        fd = _open_port(cfg.screen_port, cfg.screen_baud)
        command = ("whmi-wri %d,%d,0\xff\xff\xff" % (len(data), cfg.transfer_baud)).encode("latin-1")
        _write_all(fd, command, IO_TIMEOUT)
        time.sleep(0.01)
        if cfg.transfer_baud != cfg.screen_baud:
            # Keep the baud-switch sequence of the hardware-tested sender.
            old_fd, fd = fd, None
            os.close(old_fd)
            fd = _open_port(cfg.screen_port, cfg.transfer_baud)
        _wait_ack(fd, "waiting for the screen to accept the firmware download")

        for offset in range(0, len(data), BLOCK_SIZE):
            block = data[offset:offset + BLOCK_SIZE]
            timeout = IO_TIMEOUT + len(block) * 10 / cfg.transfer_baud
            _write_all(fd, block, timeout)
            time.sleep(0.005)
            _wait_ack(fd, "waiting for ACK at %d / %d bytes" % (offset + len(block), len(data)),
                      ACK_TIMEOUT + len(block) * 10 / cfg.transfer_baud)
            confirmed += len(block)
            if confirmed == len(data) or confirmed % (512 * 1024) == 0:
                print("%s %d / %d bytes (%d%%) acknowledged" %
                      (time.strftime("%H:%M:%S"), confirmed, len(data), 100 * confirmed // len(data)), flush=True)
        print("Screen firmware download acknowledged in full", flush=True)
        return 0
    except KeyboardInterrupt:
        print("xindi: screen flash interrupted (%d bytes acknowledged)" % confirmed, file=sys.stderr)
        return 130
    except (OSError, termios.error) as e:
        print("xindi: screen flash failed (%d bytes acknowledged): %s" % (confirmed, e), file=sys.stderr)
        return 1
    finally:
        if fd is not None:
            os.close(fd)
