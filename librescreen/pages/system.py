"""The system settings page."""

from librescreen import state as g
from librescreen.config import settings


def common_setting():
    g.shown.oobe_enabled = settings.get_oobe_enabled()
    state = "oobe_on" if g.shown.oobe_enabled else "oobe_off"
    if g.shown.changed("reset_btn", state):
        g.port.face("reset_btn", state)
