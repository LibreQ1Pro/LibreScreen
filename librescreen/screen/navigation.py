"""Switching the page of the screen and the version the screen compares."""

import logging
import time

from librescreen import state as g
from librescreen.screen import pageids as ids
from librescreen.util.cpp import to_string

log = logging.getLogger(__name__)


# The version of the port as semver. The screen cannot compare semver, so it gets major * 10000 + minor * 100 + patch
# (1.7.10 -> 10710, 0.1.0 -> 100); the main page of the screen firmware shows a warning when it differs from the number
# it was built for (display_firmware/pages/main.json). The screen forgets it on every power-up, so it is sent again
# whenever the main page is opened and when the screen reports a start.
VERSION = (0, 1, 0)


def version_number(version):
    """The number the screen compares: major (0-99), minor (0-99), patch (0-99)."""
    major, minor, patch = version
    if not (0 <= major <= 99 and 0 <= minor <= 99 and 0 <= patch <= 99):
        raise ValueError("version %r does not fit the screen: every part must be 0..99" % (version,))
    return major * 10000 + minor * 100 + patch


UI_VERSION = str(version_number(VERSION))


def send_ui_version():
    g.port.val("boot_logo.version", UI_VERSION)


LANGUAGE_FRAME = 0xa0


def request_language():
    """Asks the screen for its language: it answers with the frame ``a0 lang`` (the same frame it sends when the
    user picks a language). The screen is the only place the language is stored (``lang``, in its EEPROM)."""
    g.port.raw("prints 0x%x,1" % LANGUAGE_FRAME)
    g.port.raw("prints lang,1")
    for _ in range(3):
        g.port.raw("prints 0xff,1")


PAGE_CHECK_INTERVAL = 2.0       # seconds between two questions "which page do you show?"
# Pages the screen switches to by itself: the "next / previous" arrows of the language lists (the host works for the first of the two, the buttons of both
# send its id) and the number keyboard that a value of a print page opens and closes on its own (key=2). The answer "that page" is not a wrong page.
SELF_SWITCHED = {frozenset((ids.LANGUAGE, ids.LANGUAGE2)), frozenset((ids.OPEN_LANGUAGE, ids.OPEN_LANGUAGE2)),
                 frozenset((ids.PRINTING, ids.PRINTING_KB)), frozenset((ids.PRINTING_2, ids.PRINTING_KB))}
PAGE_SETTLE = 1.5               # a switch takes a moment: what the screen says earlier is about the page before


def page_to(page_id):
    if page_id == ids.MAIN:
        send_ui_version()
    g.screen.previous_page = g.screen.page
    g.screen.page = page_id
    g.screen.page_switched_at = time.monotonic()
    g.screen.page_mismatch = 0
    g.shown.page_values.clear()         # the page starts from its stored values
    g.port.page(to_string(page_id))


def ask_page():
    g.port.sendme()


def page_reported(page_id):
    """The screen says which page it shows (the answer to ``sendme``). When it is not the page the host works for (a switch that did not happen, a page
    that was left by itself), it has to be switched again: the host would otherwise refresh and answer clicks for a page nobody sees.
    Two answers in a row are needed (one may be a switch in progress). Returns True when the page was switched again."""
    if page_id == g.screen.page or frozenset((page_id, g.screen.page)) in SELF_SWITCHED:
        g.screen.page_mismatch = 0
        return False
    if time.monotonic() - g.screen.page_switched_at < PAGE_SETTLE:
        return False
    g.screen.page_mismatch += 1
    if g.screen.page_mismatch < 2:
        ask_page()
        return False
    log.warning("The screen shows the page %d, the page %d is expected: switching again", page_id, g.screen.page)
    g.screen.page_mismatch = 0
    g.screen.page_switched_at = time.monotonic()
    g.shown.page_values.clear()
    g.port.page(to_string(g.screen.page))
    return True
