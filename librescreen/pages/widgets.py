"""Helpers shared by the pages: widget pairs, picture transfer to the screen."""

import contextlib
import time

from librescreen import state as g
from librescreen.util.cpp import substr


def face_group(names, selected, on="on", off="off"):
    """Of a row of buttons the selected one looks ``on``, the others ``off``."""
    for i, name in enumerate(names):
        g.port.face(name, on if i == selected else off)


def temperature(value):
    """A temperature for a value field of the screen: an integer, or ``---`` when the reading is not there (never a stale or invented 0)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "---"
    return str(round(value)) if value == value and abs(value) != float("inf") else "---"


def heat_readout(prefix, current, target):
    """The fields ``<prefix>_temp`` (current) and ``<prefix>_set`` (``/ target``) of a heater readout."""
    g.port.txt(prefix + "_temp", temperature(current))
    g.port.txt(prefix + "_set", "/ " + temperature(target))


HOT = "64459"       # the colour of a heater that is on (#ff7a59 in RGB565)
TEXT = "63422"      # the normal colour of a value (#f4f4f7)


def heater_row(prefix, current, target, icon=None):
    """A heater of a card: the readout, the colour of the current value and the icon (``<icon>_icon``: on when the heater has a target)."""
    active = temperature(target) not in ("---", "0")
    heat_readout(prefix, current, target)
    g.port.pco(prefix + "_temp", HOT if active else TEXT)
    g.port.face((icon or prefix) + "_icon", "on" if active else "off")


def fan_values():
    """The speed of the three fans in percent, for the fan tiles."""
    for number, value in (("1", g.klippy.out_pin_fan0_value), ("2", g.klippy.out_pin_fan2_value), ("3", g.klippy.out_pin_fan3_value)):
        g.port.txt("fan" + number + "_val", str(round(value * 100)))


def show_readout(prefix, shown):
    """Shows or hides the three fields of a heater readout that the page keeps hidden until it is needed."""
    for part in ("_temp", "_set", "_unit"):
        g.port.vis(prefix + part, "1" if shown else "0")


def cut_after_point(text, n):
    """``s.substr(0, s.find(".") + n)``"""
    return substr(text, 0, text.find(".") + n)


def send_chunks_txt(data, target="cp_data"):
    """Sends a picture string in 2048 byte pieces through the "add" text variable into the text ``target`` (of the preview page)."""
    num = 2048
    length = len(data)
    end = num
    start = 0
    while start < length:
        if end > length:
            s = substr(data, start, length - start)
            g.port.txt("cp_pad", s)
            g.port.drain()
            g.port.txt_plus(target, target, "cp_pad")
            g.port.drain()
            break
        s = substr(data, start, num)
        start = end
        end = end + num
        g.port.txt("cp_pad", s)
        g.port.drain()
        g.port.txt_plus(target, target, "cp_pad")
        g.port.drain()


def send_chunks_cp(obj, data):
    """Writes a picture string in 2048 byte pieces into a picture widget."""
    num = 2048
    length = len(data)
    end = num
    start = 0
    while start < length:
        if end > length:
            part = substr(data, start, length - start)
            g.port.drain()
            g.port.cp_image(obj, part)
            break
        part = substr(data, start, num)
        start = end
        end = end + num
        g.port.drain()
        g.port.cp_image(obj, part)


def two_state_button(button, is_on):
    g.port.face(button, "on" if is_on else "off")


@contextlib.contextmanager
def fast_screen_link():
    """The pictures go over the serial line at 921600 baud."""
    g.port.baud(921600)
    time.sleep(0.05)
    g.port.set_baud(921600)
    try:
        yield
    finally:
        g.port.baud(115200)
        time.sleep(0.05)
        g.port.set_baud(115200)


def segmented(seg, options, selected):
    """A segmented control: ``options`` = [(look, label widget)]; the pill shows the look ``selected``, its label is white and the others are muted
    (the labels have no background of their own, the pill or the track shows under them)."""
    g.port.face(seg, selected)
    for look, label in options:
        g.port.pco(label, "65535" if look == selected else "42294")


def list_row(row, state):
    """A row of a list of networks: its look (``item``, ``check``, ``blank``); the text of a blank row is hidden (its box would show on the page colour)."""
    g.port.face(row, state)
    g.port.vis(row + "_txt", "0" if state == "blank" else "1")
