"""Instructions for the TJC (USART HMI) screen.

Every instruction is terminated by three 0xFF bytes.  Like the original the
methods wait for the output to drain (tcdrain) and then issue a single
write(); errors are ignored.
"""

import logging
import os
import select
import termios
import time

from librescreen.config import runtime
from librescreen.screen import faces
from librescreen.screen.serial import set_option
from librescreen.util.cpp import s2b, to_string

log = logging.getLogger(__name__)

END = b"\xff\xff\xff"

# The refresh of the pages runs every 50 ms and sets the same values again and again. Only a change is sent: the
# setters remember what the screen got last for each ``object.attribute``. The memory is dropped when the screen may
# have changed on its own (a new page, anything the screen reports, i.e. a touch or a typed value) and every
# FULL_REFRESH seconds, so that an instruction lost on the way is repeated soon.
FULL_REFRESH = 5.0
WRITE_TIMEOUT = 5.0         # s, how long one write waits for room in the buffer of the line

# Python only: LIBRESCREEN_TJC_LOG=1 prints every instruction sent to the screen
# (debugging aid, off by default: the main loop sends hundreds per second)
_TJC_LOG = os.environ.get("LIBRESCREEN_TJC_LOG") == "1"


class ScreenPort:
    """The serial port of the screen and the instructions it understands."""

    def __init__(self, fd=-1):
        self.fd = fd
        self._logged = {}
        self._sent = {}             # "object.attribute" -> the last instruction that set it
        self._sent_since = time.monotonic()

    def open(self, path=None, baud=None):
        """Open the port (the one of the configuration); returns False when it cannot be opened."""
        path = path or runtime.cfg.screen_port
        baud = baud or runtime.cfg.screen_baud
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NDELAY | os.O_NOCTTY)
        except OSError:
            self.fd = -1
            return False
        set_option(self.fd, baud, 8, 'N', 1)
        return True

    def set_baud(self, baud):
        set_option(self.fd, baud, 8, 'N', 1)

    # -- raw bytes ---------------------------------------------------------------------------------------------

    def drain(self):
        try:
            termios.tcdrain(self.fd)
        except (termios.error, OSError, ValueError):
            pass

    def write(self, data):
        """Writes all of ``data``: the port is non-blocking, so a write may take only a part of it (the buffer of the
        line is full) or fail with EAGAIN; the rest is written when the line has room again."""
        data = bytes(data)
        sent = 0
        deadline = time.monotonic() + WRITE_TIMEOUT
        while sent < len(data):
            try:
                sent += os.write(self.fd, data[sent:])
            except BlockingIOError:
                if time.monotonic() > deadline:
                    return -1
                try:
                    select.select([], [self.fd], [], 0.5)
                except (OSError, ValueError):
                    return -1
            except (OSError, ValueError):
                return -1
        return sent

    def _send(self, cmd):
        if _TJC_LOG:
            # the same instruction is logged at most once a second (journald drops
            # lines when a service writes too many)
            now = time.time()
            if now - self._logged.get(cmd, 0.0) >= 1.0:
                self._logged[cmd] = now
                print("TJC> " + cmd.rstrip(b"\xff").decode("utf-8", "replace"), flush=True)
        self.drain()
        self.write(cmd)

    def forget(self):
        """The screen may differ from what was sent: the next setters are sent again."""
        self._sent.clear()
        self._sent_since = time.monotonic()

    def _set(self, key, cmd):
        """Sends a setter unless the screen already has exactly this."""
        now = time.monotonic()
        if now - self._sent_since > FULL_REFRESH:
            self.forget()
        if self._sent.get(key) == cmd:
            return
        self._sent[key] = cmd
        self._send(cmd)

    # -- instructions ------------------------------------------------------------------------------------------

    def sendme(self):
        """Asks the screen which page it shows: it answers ``66 <page> ff ff ff``."""
        self._send(s2b("sendme") + END)

    def page(self, pageid):
        """Switch page"""
        self.forget()
        self._send(s2b("page " + pageid) + END)

    def vis(self, obj, state):
        """Hide / show a widget"""
        self._set("vis " + obj, s2b("vis " + obj + "," + state) + END)

    def tsw(self, obj, state):
        """Enable / disable touch for a widget"""
        self._set("tsw " + obj, s2b("tsw " + obj + "," + state) + END)

    def twfile(self, filepath, filesize):
        """Pass-through file transfer (X3/X5 only)"""
        cmd = s2b("twfile \"" + filepath + "\"," + filesize) + END
        log.info("%s", cmd.decode("utf-8", "replace"))
        self._send(cmd)

    def delfile(self, filepath):
        """Delete a file (X3/X5 only)"""
        cmd = s2b("delfile \"" + filepath + "\"") + END
        log.info("%s", cmd.decode("utf-8", "replace"))
        self._send(cmd)

    def raw(self, instruction):
        """Any instruction of the screen, e.g. a global variable assignment ``kbmode=2``"""
        self._send(s2b(instruction) + END)

    def txt(self, obj, txt):
        """Change the text of a widget. The screen has no escape for a quote inside a string (the instruction is
        rejected as "trailing tokens"), so a quote in the text becomes an apostrophe."""
        self._set(obj + ".txt", s2b(obj + ".txt=" + "\"" + txt.replace("\"", "'") + "\"") + END)

    def face(self, obj, state):
        """Show a look of a widget: the tiles of its released and its pressed state (librescreen/screen/faces.py)."""
        released, pressed = faces.FACES[obj][state]
        self._set(obj + ".pic", s2b(obj + ".pic=" + released) + END)
        if pressed is not None:
            self._set(obj + ".pic2", s2b(obj + ".pic2=" + pressed) + END)

    def val(self, obj, val):
        """Change the value of a variable"""
        self._set(obj + ".val", s2b(obj + ".val=" + val) + END)

    def pco(self, obj, poc):
        """Change the colour"""
        self._set(obj + ".pco", s2b(obj + ".pco=" + poc) + END)

    def cp_close(self, obj):
        self._send(s2b(obj + ".close()") + END)

    def write_begin(self, obj):
        self._send(s2b(obj + ".write(\""))

    def write_end(self):
        self._send(b"\")" + END)

    def cp_image(self, obj, image):
        self.write_begin(obj)
        self.drain()
        self.write(s2b(image))
        self.write_end()

    def txt_plus(self, obj1, obj2, obj3):
        self._send(s2b(obj1 + ".txt=" + obj2 + ".txt+" + obj3 + ".txt") + END)

    def baud(self, baud):
        self._send(s2b("baud=" + to_string(baud)) + END)
