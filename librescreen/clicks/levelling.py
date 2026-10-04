"""Clicks on the levelling, z-offset, bed calibration and input shaping pages. Each function gets the page id and the widget id the screen sent; HANDLERS maps pages to them."""

import logging
import os

from librescreen import state as g
from librescreen.pages import file_list, navigation
from librescreen.printer import calibration, heating, klipper
from librescreen.util.cpp import to_string
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to

log = logging.getLogger(__name__)


def level_mode(page_id, widget_id):
    if widget_id == ids.ALL_TO_MAIN:
        page_to(ids.MAIN)
    elif widget_id == ids.ALL_TO_FILE_LIST:
        file_list.go_to_file_list()
    elif widget_id == ids.ALL_TO_ADJUST:
        navigation.go_to_adjust()
    elif widget_id == ids.ALL_TO_SETTING:
        pass
    elif widget_id == ids.LEVEL_MODE_AUTO_LEVEL:
        klipper.get_object_status()
        page_to(ids.AUTO_HEATERBED)
    elif widget_id == ids.LEVEL_MODE_SYNTONY:
        calibration.go_to_syntony_move()
    elif widget_id == ids.LEVEL_MODE_BED_CALIBRATION:
        page_to(ids.CALIBRATE_WARNING)
    elif widget_id == ids.LEVEL_MODE_TO_COMMON_SETTING:
        page_to(ids.COMMON_SETTING)
        g.screen.set_mode = "Common_setting"
    elif widget_id == ids.LEVEL_MODE_ZOFFSET:
        page_to(ids.ZOFFSET)


def zoffset(page_id, widget_id):
    if widget_id == ids.ZOFFSET_BACK:
        page_to(ids.LEVEL_MODE)


def auto_heaterbed(page_id, widget_id):
    if widget_id == ids.AUTO_HEATERBED_DOWN:
        heating.set_auto_level_heater_bed_target(False)
    elif widget_id == ids.AUTO_HEATERBED_UP:
        heating.set_auto_level_heater_bed_target(True)
    elif widget_id == ids.AUTO_HEATERBED_ON_OFF:
        heating.filament_heater_bed_target()
    elif widget_id == ids.AUTO_HEATERBED_BACK:
        page_to(ids.LEVEL_MODE)
    elif widget_id == ids.AUTO_HEATERBED_NEXT:
        if g.klippy.heater_bed_target < 35:
            page_to(ids.AUTO_WARNING)
        else:
            g.screen.auto_level_button_enabled = True
            g.klippy.idle_timeout_state = "Printing"
            calibration.start_auto_level()


def auto_finish(page_id, widget_id):
    if widget_id == ids.AUTO_FINISH_YES:
        log.debug("Auto levelling finished")
        page_to(ids.LEVEL_MODE)


def pre_bed_calibration(page_id, widget_id):
    if widget_id == ids.PRE_BED_CALIBRATION_SET_001:
        calibration.set_auto_level_dist(0.01)
    elif widget_id == ids.PRE_BED_CALIBRATION_SET_005:
        calibration.set_auto_level_dist(0.05)
    elif widget_id == ids.PRE_BED_CALIBRATION_SET_01:
        calibration.set_auto_level_dist(0.1)
    elif widget_id == ids.PRE_BED_CALIBRATION_SET_05:
        calibration.set_auto_level_dist(0.5)
    elif widget_id == ids.PRE_BED_CALIBRATION_UP:
        calibration.bed_adjust(True)
    elif widget_id == ids.PRE_BED_CALIBRATION_DOWN:
        calibration.bed_adjust(False)
    elif widget_id == ids.PRE_BED_CALIBRATION_ENTER:
        calibration.bed_calibrate()


def bed_calibration(page_id, widget_id):
    if widget_id == ids.BED_CALIBRATION_NEXT:
        calibration.bed_calibrate()


def go_to_screw(i):
    x, y = g.levelling.bed_screws[i]
    g.klippy.idle_timeout_state = "Printing"
    klipper.send_gcode("G1 Z10 F600\n")
    klipper.send_gcode("G1 X" + to_string(x) + " Y" + to_string(y) + " F9000\n")
    klipper.send_gcode("G1 Z0 F600\n")
    g.screen.manual_count = -1
    page_to(ids.BED_MOVING)


def bed_finish(page_id, widget_id):
    if widget_id == ids.BED_FINISH_OK:
        page_to(ids.LEVEL_MODE)
    elif widget_id == ids.BED_FINISH_SCREW1:
        go_to_screw(0)
    elif widget_id == ids.BED_FINISH_SCREW2:
        go_to_screw(1)
    elif widget_id == ids.BED_FINISH_SCREW3:
        go_to_screw(2)
    elif widget_id == ids.BED_FINISH_Z_TILT:
        g.klippy.idle_timeout_state = "Printing"
        klipper.send_gcode("G28\nZ_TILT_ADJUST\n")
        klipper.send_gcode("G1 Z10 F600\nG1 X0 Y0 F9000\n")
        g.screen.manual_count = -2
        page_to(ids.BED_MOVING)


def syntony_move(page_id, widget_id):
    if widget_id == ids.SYNTONY_MOVE_JUMP_OUT:
        klipper.send_gcode("SAVE_CONFIG\n")
        page_to(ids.SYNTONY_FINISH)


def syntony_finish(page_id, widget_id):
    if widget_id == ids.SYNTONY_FINISH_YES:
        page_to(ids.LEVEL_MODE)
        os.sync()
        klipper.sub_object_status()
        klipper.get_object_status()


def level_error(page_id, widget_id):
    if widget_id == ids.LEVEL_ERROR_YES:
        page_to(ids.MAIN)


def auto_warning(page_id, widget_id):
    if widget_id == ids.AUTO_WARNING_YES:
        page_to(ids.AUTO_HEATERBED)


def calibrate_warning(page_id, widget_id):
    if widget_id == ids.CALIBRATE_WARNING_NEXT:
        g.screen.manual_count = 4
        calibration.bed_calibrate()
    elif widget_id == ids.CALIBRATE_WARNING_BACK:
        page_to(ids.LEVEL_MODE)


HANDLERS = {
    ids.LEVEL_MODE: level_mode,
    ids.ZOFFSET: zoffset,
    ids.AUTO_HEATERBED: auto_heaterbed,
    ids.AUTO_FINISH: auto_finish,
    ids.PRE_BED_CALIBRATION: pre_bed_calibration,
    ids.BED_CALIBRATION: bed_calibration,
    ids.BED_FINISH: bed_finish,
    ids.SYNTONY_MOVE: syntony_move,
    ids.SYNTONY_FINISH: syntony_finish,
    ids.LEVEL_ERROR: level_error,
    ids.AUTO_WARNING: auto_warning,
    ids.CALIBRATE_WARNING: calibrate_warning,
}
