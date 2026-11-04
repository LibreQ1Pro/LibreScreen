"""Shared by the click handlers."""

from librescreen import state as g
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to


def printer_not_failed():
    return g.klippy.webhooks_state != "shutdown" and g.klippy.webhooks_state != "error"


def nav_guarded(widget_id):
    """ALL_TO_* buttons of the pages that are reachable while Klipper is in an error state."""
    from librescreen.pages import file_list
    from librescreen.pages import navigation
    if widget_id == ids.ALL_TO_MAIN:
        if printer_not_failed():
            page_to(ids.MAIN)
        return True
    if widget_id == ids.ALL_TO_FILE_LIST:
        if printer_not_failed():
            file_list.go_to_file_list()
        return True
    if widget_id == ids.ALL_TO_ADJUST:
        if printer_not_failed():
            navigation.go_to_adjust()
        return True
    return False
