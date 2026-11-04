"""Clicks on the main page, the file list, the preview and the pages of a print. Each function gets the page id and the widget id the screen sent; HANDLERS maps pages to them."""

import logging
import time

from librescreen import state as g
from librescreen.moonraker import gcode_files
from librescreen.pages import file_list as pages_file_list, navigation, preview as pages_preview, printing as pages_printing
from librescreen.printer import heating, job, klipper, motion
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to

log = logging.getLogger(__name__)


def main(page_id, widget_id):
    if widget_id == ids.ALL_TO_MAIN:
        pass
    elif widget_id == ids.ALL_TO_FILE_LIST:
        pages_file_list.go_to_file_list()
    elif widget_id == ids.ALL_TO_ADJUST:
        navigation.go_to_adjust()
    elif widget_id == ids.ALL_TO_SETTING:
        navigation.go_to_setting()
    elif widget_id == ids.MAIN_CASELIGHT:
        heating.led_on_off()
    elif widget_id == ids.MAIN_BEEP:
        heating.beep_on_off()
    elif widget_id == ids.MAIN_STOP:
        motion.motors_off()
    elif widget_id in (ids.MAIN_SET_TEMP, ids.MAIN_SET_TEMP_2, ids.MAIN_SET_TEMP_3):
        # the heater tiles open the temperature keyboard (its mode is sys1: 0 nozzle, 1 bed, 2 chamber); it returns to Home
        g.screen.adjust_mode = "Filament"
        g.screen.temperature_from_main = True
        g.port.raw("sys1=%d" % (widget_id - ids.MAIN_SET_TEMP))
        page_to(ids.FILAMENT_KB)
    elif widget_id == ids.MAIN_TOGGLE_NOZZLE:
        heating.filament_extruder_target()
    elif widget_id == ids.MAIN_TOGGLE_BED:
        heating.filament_heater_bed_target()
    elif widget_id == ids.MAIN_TOGGLE_CHAMBER:
        heating.filament_hot_target()
    elif widget_id == ids.MAIN_CACHE:
        g.files.list_pages = 0
        g.files.list_current_pages = 0
        g.files.list_folder_layers = 0
        g.files.list_previous_path = ""
        g.files.list_root_path = pages_file_list.DEFAULT_DIR
        g.files.list_path = ""
        pages_file_list.refresh_page_files(g.files.list_current_pages)
        if g.files.list_last_printed:
            pages_file_list.clear_cp0_image()
            gcode_files.open_last_printed()
            g.screen.file_mode = "Local"


def file_list(page_id, widget_id):
    if widget_id == ids.ALL_TO_MAIN:
        page_to(ids.MAIN)
    elif widget_id == ids.ALL_TO_FILE_LIST:
        pass
    elif widget_id == ids.ALL_TO_ADJUST:
        navigation.go_to_adjust()
    elif widget_id == ids.ALL_TO_SETTING:
        navigation.go_to_setting()
    elif widget_id == ids.FILE_LIST_BACK:
        if g.files.list_folder_layers == 0 or (g.files.list_folder_layers == 1 and g.screen.file_mode != "Local"):
            pass
        else:
            gcode_files.get_parenet_dir_files_list()
    elif widget_id in (ids.FILE_LIST_BTN_1, ids.FILE_LIST_BTN_2, ids.FILE_LIST_BTN_3,
                       ids.FILE_LIST_BTN_4):
        pages_file_list.clear_cp0_image()
        gcode_files.get_sub_dir_files_list(widget_id - ids.FILE_LIST_BTN_1)
        g.screen.bed_leveling = True
    # 4.4.22: the list is marked as changed and the touch is disabled
    # until the pictures of the new page are sent
    elif widget_id == ids.FILE_LIST_PREVIOUS:
        if pages_file_list.detect_disk() == -1 and g.screen.file_mode == "USB":
            g.screen.file_list_refreshed = False
            pages_file_list.go_to_file_list()
        elif g.files.list_current_pages > 0:
            g.screen.file_list_refreshed = False
            g.files.list_current_pages -= 1
            page_to(ids.FILE_LIST)
            g.port.tsw("255", "0")
            pages_file_list.refresh_page_files(g.files.list_current_pages)
            pages_file_list.refresh_files_list()
        log.debug("%d", g.files.list_folder_layers)
    elif widget_id == ids.FILE_LIST_NEXT:
        if pages_file_list.detect_disk() == -1 and g.screen.file_mode == "USB":
            g.screen.file_list_refreshed = False
            pages_file_list.go_to_file_list()
        elif g.files.list_current_pages < g.files.list_pages:
            g.screen.file_list_refreshed = False
            g.files.list_current_pages += 1
            page_to(ids.FILE_LIST)
            g.port.tsw("255", "0")
            pages_file_list.refresh_page_files(g.files.list_current_pages)
            pages_file_list.refresh_files_list()
        log.debug("%d", g.files.list_folder_layers)
    # 4.4.2 CLL local / USB buttons on the file list page
    elif widget_id == ids.FILE_LIST_LOCAL:
        if g.screen.file_mode != "Local":
            g.screen.file_mode = "Local"
            g.screen.file_list_refreshed = False
            pages_file_list.go_to_file_list()
    elif widget_id == ids.FILE_LIST_USB:
        if g.screen.file_mode != "USB":
            g.screen.file_mode = "USB"
            g.screen.file_list_refreshed = False
            pages_file_list.go_to_file_list()


def _back_to_printing():
    page_to(ids.PRINTING)
    g.screen.jump_print = False


def _leave_preview():
    """Back to the file list: clear the data of the preview."""
    gcode_files.get_parenet_dir_files_list()
    pages_preview.clear_preview()
    g.screen.show_preview_complete = False
    pages_file_list.clear_cp0_image()


def _start_print():
    g.screen.muted = False             # 4.4.22 silent mode is per print
    job.print_start()
    time.sleep(1)
    if g.klippy.filament_detected:
        log.info("No filament runout detected")
        g.klippy.print_stats_state = "printing"
        job.check_filament_type()
        job.start_printing(g.files.list_print_files_path)
        g.screen.show_preview_complete = False
    else:
        log.info("Filament runout detected")
        page_to(ids.PRINT_NO_FILAMENT)


# what the navigation buttons do while no print is running
PREVIEW_NAVIGATION = {
    ids.ALL_TO_MAIN: lambda: page_to(ids.MAIN),
    ids.ALL_TO_ADJUST: navigation.go_to_adjust,
    ids.ALL_TO_SETTING: navigation.go_to_setting,
}


def preview(page_id, widget_id):
    if g.screen.page != ids.PREVIEW:
        return
    if widget_id == ids.PREVIEW_TIMELAPSE:
        job.switch_timelapse_state()
        return
    printing_or_paused = g.klippy.print_stats_state in ("printing", "paused")

    if widget_id in PREVIEW_NAVIGATION:
        if printing_or_paused:
            _back_to_printing()
        else:
            PREVIEW_NAVIGATION[widget_id]()
    elif widget_id == ids.PREVIEW_BACK:
        # 4.4.3 CLL keep the preview page from getting stuck
        if printing_or_paused:
            _back_to_printing()
        elif not g.files.meta_parse_finished or g.screen.show_preview_complete:     # the button only works once the preview is loaded
            _leave_preview()
    elif widget_id == ids.PREVIEW_START:
        if printing_or_paused:
            _back_to_printing()
        elif g.screen.show_preview_complete:
            _start_print()
        g.screen.main_picture_detected = False
        g.screen.main_picture_refreshed = False
    elif widget_id == ids.PREVIEW_BED_LEVELING:
        if printing_or_paused:
            _back_to_printing()
        else:
            g.screen.bed_leveling = not g.screen.bed_leveling


def preview_pop(page_id, widget_id):
    if widget_id == ids.PREVIEW_POP_YES:
        page_to(ids.PRINTING)
    elif widget_id == ids.PREVIEW_POP_NO_POP:
        if g.screen.page == ids.PREVIEW_POP_1:
            g.screen.preview_pop_1_on = False
        elif g.screen.page == ids.PREVIEW_POP_2:
            g.screen.preview_pop_2_on = False
        page_to(ids.PRINTING)


def printing(page_id, widget_id):
    if widget_id in (ids.PRINTING_EXTRUDER, ids.PRINTING_HEATER_BED, ids.PRINTING_FAN_1,
                     ids.PRINTING_FAN_2, ids.PRINTING_FAN_3, ids.PRINTING_HOT):
        g.screen.printing_keyboard_enabled = True
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINTING_NEXT:
        page_to(ids.PRINTING_2)
    elif widget_id == ids.PRINTING_EMERGENCY_STOP:
        page_to(ids.STOP_CONFIRM)
    elif widget_id == ids.PRINTING_PAUSE_RESUME:
        g.klippy.ready = False
        job.set_print_pause()
        page_to(ids.PRINT_FILAMENT)
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINTING_STOP:
        page_to(ids.PRINT_STOP)
        pages_printing.clear_printing_arg()


def printing_kb(page_id, widget_id):
    if widget_id == ids.PRINTING_KB_BACK:
        g.screen.printing_keyboard_enabled = False
        log.debug("Restored")
    elif widget_id == ids.PRINTING_KB_MUTE:
        log.debug("Silent mode switched")
        if not g.screen.muted:
            g.screen.muted = True
            heating.set_printer_speed(50)
        else:
            g.screen.muted = False
            heating.set_printer_speed(100)
    elif widget_id == ids.PRINTING_KB_PAUSE_RESUME:
        g.screen.printing_keyboard_enabled = False
        job.set_print_pause()
        page_to(ids.PRINT_FILAMENT)
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINTING_KB_STOP:
        g.screen.printing_keyboard_enabled = False
        page_to(ids.PRINT_STOP)
        pages_printing.clear_printing_arg()


def print_zoffset(page_id, widget_id):
    if widget_id == ids.PRINT_ZOFFSET_BACK:
        g.screen.printing_keyboard_enabled = False
        page_to(ids.PRINTING_2)
    elif widget_id == ids.PRINT_ZOFFSET_SET_001:
        motion.set_intern_zoffset(0.01)
    elif widget_id == ids.PRINT_ZOFFSET_SET_005:
        motion.set_intern_zoffset(0.05)
    elif widget_id == ids.PRINT_ZOFFSET_SET_01:
        motion.set_intern_zoffset(0.1)
    elif widget_id == ids.PRINT_ZOFFSET_SET_05:
        motion.set_intern_zoffset(0.5)
    elif widget_id == ids.PRINT_ZOFFSET_UP:
        motion.set_zoffset(False)
    elif widget_id == ids.PRINT_ZOFFSET_DOWN:
        motion.set_zoffset(True)
    elif widget_id == ids.PRINT_ZOFFSET_PAUSE_RESUME:
        g.klippy.ready = False
        job.set_print_pause()
        page_to(ids.PRINT_FILAMENT)
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINT_ZOFFSET_STOP:
        page_to(ids.PRINT_STOP)


def print_filament(page_id, widget_id):
    if widget_id == ids.PRINT_FILAMENT_ON_OFF:
        heating.set_print_filament_target()
    elif widget_id == ids.PRINT_FILAMENT_T_UP:
        heating.set_filament_extruder_target(True)
    elif widget_id == ids.PRINT_FILAMENT_T_DOWN:
        heating.set_filament_extruder_target(False)
    elif widget_id == ids.PRINT_FILAMENT_LOAD:
        g.screen.load_mode = True
        page_to(ids.PRE_HEAT)
    elif widget_id == ids.PRINT_FILAMENT_UNLOAD:
        g.screen.load_mode = False
        page_to(ids.PRE_HEAT)
    elif widget_id == ids.PRINT_FILAMENT_PAUSE_RESUME:
        log.debug("get_filament_detected_enable: %d", int(job.get_filament_detected_enable()))
        log.debug("get_filament_detected: %d", int(job.get_filament_detected()))
        g.klippy.ready = False
        page_to(ids.PRINTING)
        job.set_print_resume()
    elif widget_id == ids.PRINT_FILAMENT_STOP:
        page_to(ids.PRINT_STOP)
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINT_FILAMENT_RETRACT:
        klipper.send_gcode("M603\n")
    elif widget_id == ids.PRINT_FILAMENT_EXTRUDE:
        motion.set_print_filament_dist(50)
        motion.start_extrude()


def printing_2(page_id, widget_id):
    if widget_id == ids.PRINTING_2_BACK:
        page_to(ids.PRINTING)
    elif widget_id in (ids.PRINTING_2_SPEED, ids.PRINTING_2_FLOW, ids.PRINTING_2_FAN_1, ids.PRINTING_2_FAN_2, ids.PRINTING_2_FAN_3):
        g.screen.printing_keyboard_enabled = True
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINTING_2_ZOFFSET:
        page_to(ids.PRINT_ZOFFSET)
    elif widget_id == ids.PRINTING_2_PAUSE_RESUME:
        g.klippy.ready = False
        job.set_print_pause()
        page_to(ids.PRINT_FILAMENT)
        pages_printing.clear_printing_arg()
    elif widget_id == ids.PRINTING_2_STOP:
        page_to(ids.PRINT_STOP)
    elif widget_id == ids.PRINTING_2_CASE_LIGHT:
        heating.led_on_off()


def print_finish(page_id, widget_id):
    if widget_id == ids.PRINT_FINISH_YES:
        job.finish_print()


def print_stop(page_id, widget_id):
    if widget_id == ids.PRINT_STOP_YES:
        g.klippy.idle_timeout_state = "Printing"
        page_to(ids.PRINT_STOPPING)
        job.cancel_print()
    elif widget_id == ids.PRINT_STOP_NO:
        page_to(g.screen.previous_page)


# 4.4.22 emergency stop from the printing page
def stop_confirm(page_id, widget_id):
    if widget_id == ids.STOP_CONFIRM_YES:
        page_to(ids.PRINT_STOPPING)
        g.klippy.print_stats_state = "paused"
        motion.motors_off()
    elif widget_id == ids.STOP_CONFIRM_NO:
        page_to(ids.PRINTING)


def print_no_filament(page_id, widget_id):
    if widget_id == ids.PRINT_NO_FILAMENT_YES:
        g.klippy.filament_detected = True
        if g.screen.previous_page == ids.PREVIEW:
            klipper.get_object_status()
            page_to(ids.MOVE)
        else:
            klipper.get_object_status()
            page_to(ids.PRINT_FILAMENT)


def print(page_id, widget_id):
    if page_id == ids.PRINT_NO_FILAMENT_2:
        if widget_id == ids.PRINT_NO_FILAMENT_2_YES:
            klipper.get_object_status()
            page_to(ids.PRINT_FILAMENT)
    elif widget_id == ids.PRINT_LOW_TEMP_YES:
        g.klippy.idle_timeout_state = "Ready"
        page_to(ids.PRINT_FILAMENT)


def print_log(page_id, widget_id):
    if widget_id == ids.PRINT_LOG_YES:
        klipper.go_to_reset()


def resume_print(page_id, widget_id):
    if widget_id == ids.RESUME_PRINT_YES:
        page_to(ids.RE_PRINTING)
        klipper.send_gcode("_LIBRESCREEN_RESUME_INTERRUPTED\n")
    elif widget_id == ids.RESUME_PRINT_NO:
        page_to(ids.MAIN)
        klipper.send_gcode("_LIBRESCREEN_CLEAR_LAST_FILE")
    elif widget_id == ids.RESUME_PRINT_LOADED:
        g.screen.jump_resume_print = False      # 4.4.24: the page reports that it is shown


HANDLERS = {
    ids.MAIN: main,
    ids.FILE_LIST: file_list,
    ids.PREVIEW: preview,
    ids.PREVIEW_POP_1: preview_pop,
    ids.PREVIEW_POP_2: preview_pop,
    ids.PRINTING: printing,
    ids.PRINTING_KB: printing_kb,
    ids.PRINT_ZOFFSET: print_zoffset,
    ids.PRINT_FILAMENT: print_filament,
    ids.PRINTING_2: printing_2,
    ids.PRINT_FINISH: print_finish,
    ids.PRINT_STOP: print_stop,
    ids.STOP_CONFIRM: stop_confirm,
    ids.PRINT_NO_FILAMENT: print_no_filament,
    ids.PRINT_NO_FILAMENT_2: print,
    ids.PRINT_LOW_TEMP: print,
    ids.PRINT_LOG_F: print_log,
    ids.PRINT_LOG_S: print_log,
    ids.RESUME_PRINT: resume_print,
}
