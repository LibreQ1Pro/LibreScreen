"""Automatic levelling and the bed screw calibration."""

import logging

from librescreen import state as g
from librescreen.config import settings
from librescreen.printer.heating import set_heater_bed_target
from librescreen.printer.klipper import get_object_status
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.util.cpp import f32, to_string

log = logging.getLogger(__name__)


def set_auto_level_dist(dist):
    log.debug("SET")
    g.levelling.auto_level_dist = f32(dist)


def start_auto_level():
    g.levelling.step_1 = False
    g.levelling.step_2 = False
    g.levelling.step_3 = False
    g.levelling.step_4 = False
    if not g.levelling.start_pre_auto_level:
        g.klippy.idle_timeout_state = "Printing"
    page_to(ids.AUTO_MOVING)
    set_heater_bed_target(g.config.heater_bed_target)
    # the steps of the page follow the messages of AUTO_CALIBRATE
    g.ep.run_gcode("AUTO_CALIBRATE BED=" + to_string(g.config.heater_bed_target))


    # 4.4.22: the total print time is no longer kept in config.mksini


def go_to_syntony_move():
    g.levelling.step_1 = False
    g.levelling.syntony_finished = False
    g.klippy.idle_timeout_state = "Printing"
    page_to(ids.SYNTONY_MOVE)
    g.ep.run_gcode("INPUT_SHAPER_CALIBRATE\n")


def open_more_level_finish():
    settings.set_oobe_enabled(False)     # turn the out-of-box guide off
    get_object_status()
    page_to(ids.MAIN)


def open_heater_bed_up():
    # 4.4.22: the caller shows the "moving" page, which waits until Klipper is idle
    # again (refresh_page_open_moving()); the bed is homed and aligned with the frame
    g.klippy.idle_timeout_state = "Printing"
    g.ep.run_gcode("UNBOXING_PREPARE\n")


def bed_leveling_switch(positive):
    if positive:
        g.ep.run_gcode("_LIBRESCREEN_MESH_ADAPTIVE")
        g.screen.bed_leveling = True
    else:
        g.ep.run_gcode("_LIBRESCREEN_MESH_SAVED")
        g.screen.bed_leveling = False


def bed_calibrate():
    if g.screen.manual_count == 4:
        g.levelling.bed_offset = 0.0
        g.klippy.idle_timeout_state = "Printing"
        g.ep.run_gcode("ABORT\n")
        g.ep.run_gcode("BED_SCREWS_PREPARE\n")
        page_to(ids.BED_MOVING)
    elif g.screen.manual_count == 3:
        g.klippy.idle_timeout_state = "Printing"
        g.ep.run_gcode("G1 Z10 F600")
        g.ep.run_gcode("BED_SCREWS_ADJUST\n")
        g.ep.run_gcode("G1 Z" + to_string(g.levelling.bed_offset) + " F600\n")
        log.debug("Current bed_offset:%f", g.levelling.bed_offset)
        page_to(ids.BED_MOVING)
    elif g.screen.manual_count > 0:
        g.klippy.idle_timeout_state = "Printing"
        g.ep.run_gcode("ACCEPT\n")
        g.ep.run_gcode("G1 Z" + to_string(g.levelling.bed_offset) + " F600\n")
        page_to(ids.BED_MOVING)
    elif g.screen.manual_count == 0:
        # The last of the 3 screws of the display: ABORT also ends the session when [bed_screws] has more screws
        g.ep.run_gcode("ABORT\n")
        g.ep.run_gcode("G1 Z10 F600\nG1 X0 Y0 F9000\n")
        page_to(ids.BED_FINISH)
    else:
        g.ep.run_gcode("G1 Z10 F600\n")
        page_to(ids.BED_FINISH)
    g.screen.manual_count -= 1


def bed_adjust(status):
    if status:
        g.ep.run_gcode("G91\nG1 Z" + to_string(-g.levelling.auto_level_dist) + " F600\nG90\n")
        g.levelling.bed_offset = f32(g.levelling.bed_offset - g.levelling.auto_level_dist)
        log.debug("Current bed_offset:%f", g.levelling.bed_offset)
    else:
        g.ep.run_gcode("G91\nG1 Z" + to_string(g.levelling.auto_level_dist) + " F600\nG90\n")
        g.levelling.bed_offset = f32(g.levelling.bed_offset + g.levelling.auto_level_dist)
        log.debug("Current bed_offset:%f", g.levelling.bed_offset)
