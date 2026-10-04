"""Refreshing the page that is open: the screen is redrawn about every 50 ms."""

import logging
import time

from librescreen import state as g
from librescreen.pages import file_list, wifi
from librescreen.pages.filament import auto_unload, filament, filament_pop
from librescreen.pages.guide import open_filament_video_2, open_moving
from librescreen.pages.home import main
from librescreen.pages.leveling import (auto_finish,
                                  auto_heaterbed,
                                  auto_level,
                                  auto_moving,
                                  bed_moving,
                                  syntony_move,
                                  zoffset)
from librescreen.pages.move import move_page
from librescreen.pages.preview import preview, preview_pop
from librescreen.pages.printing import print_filament, printing, printing_zoffset, stopping
from librescreen.pages.system import common_setting
from librescreen.screen import pageids as ids
from librescreen.screen.text import ERR_MSG_LINES, ERR_MSG_WIDTH, POPUP_MSG_LINES, POPUP_MSG_WIDTH, wrap_text
from librescreen.screen.navigation import page_to

log = logging.getLogger(__name__)


# pages that stay where they are when a print starts
NO_PRINT_JUMP_PAGES = frozenset((
    ids.PRINTING, ids.PRINT_ZOFFSET, ids.PRINT_FILAMENT,
    ids.PRINT_STOP, ids.PRINT_NO_FILAMENT, ids.PRINT_NO_FILAMENT_2, ids.SHUTDOWN, ids.PRINT_STOPPING, ids.MOVE_POP_1,
    ids.GCODE_ERROR, ids.DETECT_ERROR, ids.RESET, ids.PREVIEW, ids.PREVIEW_POP_1, ids.PREVIEW_POP_2,
    ids.PRINTING_2, ids.FILAMENT_POP_2, ids.FILAMENT_POP_3, ids.STOP_CONFIRM))

# pages that stay where they are when Klipper fails
NO_RESET_JUMP_PAGES = frozenset((
    ids.GCODE_ERROR, ids.DETECT_ERROR, ids.LEVEL_ERROR, ids.SHUTDOWN, ids.LANGUAGE,
    ids.COMMON_SETTING, ids.SLEEP_MODE, ids.INTERNET, ids.WIFI_LIST, ids.WIFI_KB, ids.WIFI_CONNECT,
    ids.WIFI_FAILED, ids.WIFI_SUCCESS, ids.NET_SAVED, ids.NET_DETAIL, ids.NET_CONFIRM,
    ids.NET_INFO, ids.RESTORE_CONFIG))

# moves of the "move without homing" pop-up, by the button that started it
UNHOMED_HOMING = "SET_KINEMATIC_POSITION Z=150\nSET_KINEMATIC_POSITION X=150\nSET_KINEMATIC_POSITION Y=150\n"
UNHOMED_MOVES = {
    1: "G91\nG1 X10 F3000\nG90\nM84\n",       # X_UP
    2: "G91\nG1 X-10 F3000\nG90\nM84\n",      # X_DOWN
    3: "G91\nG1 Y10 F3000\nG90\nM84\n",       # Y_UP
    4: "G91\nG1 Y-10 F3000\nG90\nM84\n",      # Y_DOWN
    5: "G91\nG1 Z-10 F600\nG90\nM84\n",       # Z_UP
    6: "G91\nG1 Z10 F600\nG90\nM84\n",        # Z_DOWN
}


def jump_to(flag, page):
    """Reset the flag, then switch the page (the flag has to be reset first, otherwise this would loop forever)."""
    setattr(g.screen, flag, False)
    page_to(page)


def unhomed_move_pop():
    if g.screen.unhomed_move_mode in UNHOMED_MOVES:
        g.ep.run_gcode(UNHOMED_HOMING)
        g.ep.run_gcode(UNHOMED_MOVES[g.screen.unhomed_move_mode])
    g.screen.unhomed_move_mode = 0
    jump_to("jump_move_pop_2", ids.MOVE_POP_2)


def detect_error_pop():
    jump_to("jump_detect_error", ids.DETECT_ERROR)
    g.port.txt("msg", wrap_text(g.screen.error_message, POPUP_MSG_WIDTH, POPUP_MSG_LINES))


def requested_jumps():
    """The other threads ask for a page by setting a flag; the page is switched here, in the main thread.

    CLL the jumps are unconditional, the flags were set after the checks were done.
    """
    if g.screen.jump_move_pop_1:
        jump_to("jump_move_pop_1", ids.MOVE_POP_1)
    if g.screen.jump_move_pop_2:
        unhomed_move_pop()
    if g.screen.jump_detect_error:
        detect_error_pop()
    if g.screen.jump_level_error:
        jump_to("jump_level_error", ids.LEVEL_ERROR)
    if g.screen.jump_filament_pop_1:
        jump_to("jump_filament_pop_1", ids.FILAMENT_POP_1)
    if g.screen.jump_print_low_temp:
        jump_to("jump_print_low_temp", ids.PRINT_LOW_TEMP)
    if g.screen.jump_resume_print and g.screen.page != ids.RESUME_PRINT:
        # 4.4.24: the flag is reset when the page reports that it is shown; until then the page is not sent again
        # (every page command restarts the page and spoils previous_page)
        page_to(ids.RESUME_PRINT)
    if g.screen.jump_memory_warning:
        jump_to("jump_memory_warning", ids.MEMORY_WARNING)


def open_print_page_when_printing():
    """A print was started from elsewhere (the web UI): show it."""
    if g.screen.page in NO_PRINT_JUMP_PAGES:
        return
    if g.klippy.print_stats_state == "printing" and g.klippy.print_stats_filename != "":
        g.screen.main_picture_detected = False
        g.screen.main_picture_refreshed = False
        g.screen.muted = False         # 4.4.22 silent mode is per print
        log.debug("Jumping to the print page\n")
        time.sleep(1)
        file_list.get_file_estimated_time(g.klippy.print_stats_filename)
        time.sleep(1)
        g.screen.jump_print = True
        g.klippy.ready = False
        page_to(ids.PREVIEW)


def show_failure_message():
    # every refresh: the sender skips what the screen has, and writes it again to a page that is shown anew (a page forgets its text)
    g.port.txt("err_msg", wrap_text(g.klippy.webhooks_state_message, ERR_MSG_WIDTH, ERR_MSG_LINES))


def open_reset_page_on_failure():
    """Jump to the restart page when the toolhead board is disconnected (Klipper shut down)."""
    state = g.klippy.webhooks_state
    if g.screen.page == ids.RESET:
        if state in ("shutdown", "error"):
            show_failure_message()
        if state == "ready":
            page_to(ids.SYS_OK)
    elif g.screen.page not in NO_RESET_JUMP_PAGES and state in ("shutdown", "error"):
        if state == "shutdown" and g.screen.page == ids.AUTO_MOVING:
            return
        page_to(ids.RESET)
        log.debug("Restart page")
        show_failure_message()


def show():
    """Refresh the page that is open (called about every 50 ms)."""
    # 4.4.22: nothing is sent to the screen while the list pictures are transferred
    if g.pictures.send_jpg_status:
        return
    requested_jumps()
    open_print_page_when_printing()
    open_reset_page_on_failure()

    refresh = REFRESH.get(g.screen.page)
    if refresh:
        refresh()


# the page that is open -> what it shows (pages not listed have nothing to refresh)
REFRESH = {
    ids.MAIN: main,
    ids.PREVIEW: preview,
    ids.PRINTING: printing,
    ids.PRINTING_2: printing,
    ids.PRINT_FILAMENT: print_filament,
    ids.MOVE: move_page,
    ids.PRINT_ZOFFSET: printing_zoffset,
    ids.AUTO_MOVING: auto_moving,
    ids.AUTO_FINISH: auto_finish,
    ids.SYNTONY_MOVE: syntony_move,
    ids.PRINT_STOPPING: stopping,
    ids.PRE_BED_CALIBRATION: auto_level,
    ids.OPEN_FILAMENTVIDEO_2: open_filament_video_2,
    ids.ZOFFSET: zoffset,
    ids.AUTO_HEATERBED: auto_heaterbed,
    ids.FILAMENT_POP_2: filament_pop,
    ids.FILAMENT_POP_3: filament_pop,
    ids.PREVIEW_POP_1: preview_pop,
    ids.PREVIEW_POP_2: preview_pop,
    ids.BED_MOVING: bed_moving,
    ids.COMMON_SETTING: common_setting,
    ids.WIFI_KB: wifi.refresh_wifi_keyboard,
    ids.FILAMENT: filament,
    ids.AUTO_UNLOAD: auto_unload,
    ids.OPEN_MOVING: open_moving,
}
