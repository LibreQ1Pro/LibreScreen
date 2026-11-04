"""Starting, pausing and ending a print, the filament sensor and the timelapse."""

import json as _json
import logging
import time
import urllib.request

from librescreen import state as g
from librescreen.config import runtime
from librescreen.moonraker.rpc_requests import json_print_a_file
from librescreen.pages import file_list, preview
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.util import paths
from librescreen.util.cpp import cdiv, cmod, read_file, stof, str_lower_ascii, substr, to_string

log = logging.getLogger(__name__)


def stack_top(stack):
    """std::stack::top() (undefined behaviour on an empty stack in C++)"""
    return stack[-1] if stack else ""


def start_printing(filepath):
    g.ep.send(json_print_a_file(filepath))


def show_time(seconds):
    return to_string(cdiv(seconds, 3600)) + "h" + to_string(cdiv(cmod(seconds, 3600), 60)) + "m"


def get_filament_detected():
    return g.klippy.fila_sensor_detected


def get_filament_detected_enable():
    return g.klippy.fila_sensor_enabled


def set_print_pause():
    g.ep.run_gcode("PAUSE")


def set_print_resume():
    g.ep.run_gcode("RESUME")


def cancel_print():
    g.klippy.print_stats_filename = ""
    # as in mainline Klipper, CANCEL_PRINT waits until a running M109/M190 ends
    g.ep.run_gcode("CANCEL_PRINT")
    # 4.4.22: the total print time is no longer kept in config.mksini
    time.sleep(0.01)
    sdcard_reset_file()


def sdcard_reset_file():
    g.ep.run_gcode("SDCARD_RESET_FILE")


def finish_print():
    sdcard_reset_file()
    file_list.clear_cp0_image()
    preview.clear_preview()
    g.screen.show_preview_complete = False
    page_to(ids.MAIN)


def detect_error():
    if g.screen.page in (ids.PRINTING, ids.PRINT_ZOFFSET, ids.PRINT_FILAMENT,
                             ids.PRINTING_2, ids.GCODE_ERROR, ids.LEVEL_ERROR,
                             ids.DETECT_ERROR):
        pass
    elif g.screen.page == ids.AUTO_MOVING:
        g.ep.run_gcode("RESTART")
        g.screen.jump_level_error = True
    else:
        if g.klippy.webhooks_state != "shutdown" and g.klippy.webhooks_state != "error":
            g.screen.jump_detect_error = True


def clear_previous_data():
    sdcard_reset_file()
    file_list.clear_cp0_image()
    preview.clear_preview()
    g.screen.show_preview_complete = False
    g.screen.printing_keyboard_enabled = False


def print_start():
    if g.screen.bed_leveling:
        g.ep.run_gcode("_LIBRESCREEN_MESH_ADAPTIVE\n")
    else:
        g.ep.run_gcode("_LIBRESCREEN_MESH_SAVED\n")


def check_filament_type():
    if g.files.meta_filament_type != "":
        filament_type = g.files.meta_filament_type
    else:
        filament_type = g.files.meta_filament_name
    filament_type = str_lower_ascii(filament_type)
    log.info("filament_type : %s", filament_type)
    # 4.4.1 CLL "do not show again" button on the filament confirmation pop-ups
    if (filament_type.find("pla") != -1 or filament_type.find("petg") != -1) and g.screen.preview_pop_1_on:
        page_to(ids.PREVIEW_POP_1)
    elif filament_type.find("abs") != -1 and g.screen.preview_pop_2_on:
        page_to(ids.PREVIEW_POP_2)
    else:
        page_to(ids.PRINTING)


def check_filament_width():
    """4.4.2 support for the hall filament width sensor"""
    if g.files.filament_message.find("// Filament dia (measured mm):") != -1:
        filament_width = stof(substr(g.files.filament_message, 31))
        log.info("Filament width: %f", filament_width)
        if filament_width < 0.3:
            g.klippy.filament_detected = False
        else:
            g.klippy.filament_detected = True
    elif g.files.filament_message.find("// Filament NOT present") != -1:
        g.klippy.filament_detected = False


TIMELAPSE_PATH = "machine/timelapse/settings"


def check_timelapse_state():
    """4.4.22: state of Moonraker's timelapse plugin (off when it is not installed)."""
    try:
        with urllib.request.urlopen(runtime.cfg.moonraker_url(TIMELAPSE_PATH), timeout=2) as resp:
            g.screen.timelapse_enabled = bool(_json.loads(resp.read().decode("utf-8"))["result"]["enabled"])
    except Exception as e:
        log.error("Timelapse state: %s", str(e))
        g.screen.timelapse_enabled = False
    return g.screen.timelapse_enabled


def switch_timelapse_state():
    """4.4.22: turn Moonraker's timelapse on / off (preview page)."""
    url = runtime.cfg.moonraker_url(TIMELAPSE_PATH) + ("?enabled=False" if g.screen.timelapse_enabled else "?enabled=True")
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=b"", method="POST"), timeout=2).close()
        g.screen.timelapse_enabled = not g.screen.timelapse_enabled
    except Exception as e:
        log.error("Timelapse switch: %s", str(e))     # no plugin: the switch stays off


def check_print_interrupted():
    printer_variables = read_file(paths.klipper_config() + "/saved_variables.cfg")
    if printer_variables is None:
        log.error("Can't open the file %s", paths.klipper_config() + "/saved_variables.cfg")
        return
    print_interrupted_status = substr(printer_variables, printer_variables.find("was_interrupted =") + 18, 5)
    if print_interrupted_status != "False":
        g.ep.run_gcode("_LIBRESCREEN_DETECT_INTERRUPTION\n")
        g.screen.jump_resume_print = True
