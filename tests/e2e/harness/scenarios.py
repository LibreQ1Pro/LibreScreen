"""
E2E scenarios.  Every scenario drives the program through the virtual screen
(touch / value / keyboard events) and the fake Moonraker (status updates,
gcode responses, notifications).  Only the recorded traces are compared, the
scenarios themselves just have to put both implementations through the same
inputs with enough time between the steps.

Page / widget ids are the ones from include/ui.h.
"""

import json
import os
import sys

sys.path.insert(0, os.environ.get("LIBRESCREEN_SRC_DIR", "/opt/src_py"))
from librescreen.screen import pageids as _ids        # noqa: E402

# pages (the numbers are the ones of librescreen/screen/pageids.py, so they follow the screen project)
LOGO = _ids.LOGO
OPEN_LANGUAGE = _ids.OPEN_LANGUAGE
OPEN_POP = _ids.OPEN_POP
OPEN_VIDEO_1 = _ids.OPEN_VIDEO_1
OPEN_VIDEO_2 = _ids.OPEN_VIDEO_2
OPEN_WARNING = _ids.OPEN_WARNING
OPEN_FILAMENTVIDEO_1 = _ids.OPEN_FILAMENTVIDEO_1
OPEN_FILAMENTVIDEO_2 = _ids.OPEN_FILAMENTVIDEO_2
OPEN_FILAMENTVIDEO_3 = _ids.OPEN_FILAMENTVIDEO_3
OPEN_FINISH = _ids.OPEN_FINISH
OPEN_FILAMENTVIDEO_0 = _ids.OPEN_FILAMENTVIDEO_0
MAIN = _ids.MAIN
FILE_LIST = _ids.FILE_LIST
PREVIEW = _ids.PREVIEW
PREVIEW_POP_1 = _ids.PREVIEW_POP_1
PREVIEW_POP_2 = _ids.PREVIEW_POP_2
PRINTING = _ids.PRINTING
PRINT_ZOFFSET = _ids.PRINT_ZOFFSET
PRINT_FILAMENT = _ids.PRINT_FILAMENT
PRINTING_2 = _ids.PRINTING_2
PRINT_FINISH = _ids.PRINT_FINISH
PRINT_STOP = _ids.PRINT_STOP
PRINT_STOPPING = _ids.PRINT_STOPPING
PRINT_NO_FILAMENT = _ids.PRINT_NO_FILAMENT
PRINT_LOW_TEMP = _ids.PRINT_LOW_TEMP
MOVE = _ids.MOVE
MOVE_POP_1 = _ids.MOVE_POP_1
MOVE_POP_2 = _ids.MOVE_POP_2
FILAMENT_KB = _ids.FILAMENT_KB
FILAMENT_POP_1 = _ids.FILAMENT_POP_1
FILAMENT_POP_2 = _ids.FILAMENT_POP_2
FILAMENT_POP_3 = _ids.FILAMENT_POP_3
LEVEL_MODE = _ids.LEVEL_MODE
ZOFFSET = _ids.ZOFFSET
AUTO_HEATERBED = _ids.AUTO_HEATERBED
AUTO_MOVING = _ids.AUTO_MOVING
AUTO_FINISH = _ids.AUTO_FINISH
PRE_BED_CALIBRATION = _ids.PRE_BED_CALIBRATION
BED_MOVING = _ids.BED_MOVING
BED_CALIBRATION = _ids.BED_CALIBRATION
BED_FINISH = _ids.BED_FINISH
SYNTONY_MOVE = _ids.SYNTONY_MOVE
SYNTONY_FINISH = _ids.SYNTONY_FINISH
INTERNET = _ids.INTERNET
NET_INFO = _ids.NET_INFO
NET_SAVED = _ids.NET_SAVED
WIFI_LIST = _ids.WIFI_LIST
WIFI_CONNECT = _ids.WIFI_CONNECT
WIFI_SUCCESS = _ids.WIFI_SUCCESS
WIFI_FAILED = _ids.WIFI_FAILED
WIFI_KB = _ids.WIFI_KB
COMMON_SETTING = _ids.COMMON_SETTING
LANGUAGE = _ids.LANGUAGE
SYS_OK = _ids.SYS_OK
RESET = _ids.RESET
SLEEP_MODE = _ids.SLEEP_MODE
UPDATE_SUCCESS = _ids.UPDATE_SUCCESS
RESTORE_CONFIG = _ids.RESTORE_CONFIG
PRINT_LOG_S = _ids.PRINT_LOG_S
PRINT_LOG_F = _ids.PRINT_LOG_F
DETECT_ERROR = _ids.DETECT_ERROR
GCODE_ERROR = _ids.GCODE_ERROR
SCREEN_SLEEP = _ids.SCREEN_SLEEP
LEVEL_ERROR = _ids.LEVEL_ERROR
FILAMENT = _ids.FILAMENT
PRINT_NO_FILAMENT_2 = _ids.PRINT_NO_FILAMENT_2
MEMORY_WARNING = _ids.MEMORY_WARNING
PRE_HEAT = _ids.PRE_HEAT
RESUME_PRINT = _ids.RESUME_PRINT
UNLOAD_MODE = _ids.UNLOAD_MODE
AUTO_UNLOAD = _ids.AUTO_UNLOAD
AUTO_WARNING = _ids.AUTO_WARNING
CALIBRATE_WARNING = _ids.CALIBRATE_WARNING

# navigation buttons present on every page
ALL_TO_MAIN, ALL_TO_ADJUST, ALL_TO_FILE_LIST, ALL_TO_SETTING = 0x1e, 0x1f, 0x20, 0x21

BOOT_TIMEOUT = 90


def boot(h, page=MAIN):
    h.wait_page(page, BOOT_TIMEOUT)
    h.settle(4.0)


# ---------------------------------------------------------------------------

def scenario_boot_main(h):
    """Normal start: main page, temperatures, LED / beeper buttons."""
    boot(h)
    h.mark("temps")
    h.mr.push_status({"extruder": {"temperature": 31.6, "target": 0.0}, "heater_bed": {"temperature": 40.4}})
    h.settle(1.5)
    h.mr.push_status({"extruder": {"target": 220.0}, "heater_generic chamber": {"temperature": 30.5, "target": 40.0}})
    h.settle(1.5)
    h.mark("led")
    h.touch(MAIN, 0x00, settle=1.0)
    h.mr.push_status({"output_pin caselight": {"value": 1.0}})
    h.settle(1.5)
    h.touch(MAIN, 0x00, settle=1.0)
    h.mr.push_status({"output_pin caselight": {"value": 0.0}})
    h.settle(1.0)
    h.mark("beep")
    h.touch(MAIN, 0x01, settle=1.0)
    h.mr.push_status({"gcode_macro _SOUND": {"enabled": 1}})
    h.settle(1.5)
    h.mark("stop")
    h.touch(MAIN, 0x02, settle=3.0)


def wait_preview_loaded(h, timeout=8):
    """the preview page ends with "vis preview_pic,x" once the preview is complete."""
    ok = h.screen.wait_value("vis preview_pic", lambda v: True, timeout)
    if not ok:
        h.errors.append("preview did not finish loading")
    h.settle(1.0)


def goto_common_setting(h):
    h.touch(MAIN, ALL_TO_SETTING, settle=1.0)
    h.wait_page(LEVEL_MODE)
    h.touch(LEVEL_MODE, 0x17, settle=1.5)
    h.wait_page(COMMON_SETTING)


def scenario_boot_oobe(h):
    """Out-of-box guide: language, pop-up, videos, filament steps, finish."""
    boot(h, OPEN_LANGUAGE)
    h.touch(OPEN_LANGUAGE, 0x01)                # skip -> pop-up
    h.wait_page(OPEN_POP)
    h.touch(OPEN_POP, 0x01)                     # no -> back to language
    h.wait_page(OPEN_LANGUAGE)
    h.touch(OPEN_LANGUAGE, 0x00, settle=1.0)    # next
    h.wait_page(OPEN_VIDEO_1)
    h.touch(OPEN_VIDEO_1, 0x00)
    h.touch(OPEN_VIDEO_2, 0x00)
    h.touch(OPEN_WARNING, 0x00, settle=1.0)     # open_heater_bed_up()
    h.wait_page(OPEN_FILAMENTVIDEO_1)
    h.touch(OPEN_FILAMENTVIDEO_1, 0x00, settle=1.0)
    h.wait_page(OPEN_FILAMENTVIDEO_2)
    h.settle(1.0)
    h.touch(OPEN_FILAMENTVIDEO_2, 0x01, settle=1.0)     # +3 degrees
    h.touch(OPEN_FILAMENTVIDEO_2, 0x01, settle=1.0)
    h.touch(OPEN_FILAMENTVIDEO_2, 0x00, settle=1.0)     # -3 degrees
    h.touch(OPEN_FILAMENTVIDEO_2, 0x03, settle=1.0)     # heater on
    h.mr.push_status({"extruder": {"target": 223.0, "temperature": 80.2}})
    h.settle(1.5)
    h.touch(OPEN_FILAMENTVIDEO_2, 0x03, settle=1.0)     # heater off
    h.mr.push_status({"extruder": {"target": 0.0}})
    h.settle(1.5)
    h.touch(OPEN_FILAMENTVIDEO_2, 0x02, settle=1.0)
    h.wait_page(OPEN_FILAMENTVIDEO_3)
    h.touch(OPEN_FILAMENTVIDEO_3, 0x01, settle=1.0)     # extrude
    # the page 0 -> 1 fall-through
    h.touch(OPEN_FILAMENTVIDEO_0, 0x00, settle=1.0)     # no break in the C++ switch: 72 -> 11 -> 12
    h.touch(OPEN_FILAMENTVIDEO_2, 0x02, settle=1.0)
    h.touch(OPEN_FILAMENTVIDEO_3, 0x00, settle=1.0)     # next -> finish
    h.wait_page(OPEN_FINISH)
    h.touch(OPEN_FINISH, 0x00, settle=2.0)              # open_more_level_finish()
    h.wait_page(MAIN)
    h.settle(3.0)


def scenario_screen_update(h):
    """The screen firmware was downloaded with --flash-screen (see harness.start_sut), the service starts afterwards."""
    boot(h)
    h.screen.send(b"\x91" + b"\xff\xff\xff")    # screen reports "update finished"
    h.settle(1.5)
    h.touch(UPDATE_SUCCESS, 0x00, settle=2.0)   # finish_tjc_update()
    h.wait_page(MAIN)
    h.settle(2.0)


def scenario_boot_interrupted(h):
    """Power loss recovery question after boot."""
    boot(h, RESUME_PRINT)
    h.touch(RESUME_PRINT, 0x02, settle=0.5)     # the page reports that it is shown (its codesload)
    h.touch(RESUME_PRINT, 0x01, settle=1.5)     # no
    h.wait_page(MAIN)
    h.screen.send(bytes([0x65, RESUME_PRINT, 0x00, 0x01]) + b"\xff\xff\xff")  # yes button of the resume page
    h.settle(1.5)
    h.settle(1.0)


def scenario_no_cache(h):
    """Start without a cached "last printed" file."""
    boot(h)
    h.touch(MAIN, 0x06, settle=1.5)     # cache button does nothing without a cached file
    h.touch(MAIN, ALL_TO_FILE_LIST, settle=4.0)
    h.wait_page(FILE_LIST)
    h.settle(4.0)


def scenario_file_list(h):
    """File list: pages, folders, USB / local, thumbnails, preview, back."""
    boot(h)
    h.touch(MAIN, ALL_TO_FILE_LIST, settle=1.0)
    h.wait_page(FILE_LIST)
    h.settle(6.0)                       # thumbnails are sent by the jpg thread
    h.touch(FILE_LIST, 0x0b, settle=5.0)    # next page
    h.touch(FILE_LIST, 0x0b, settle=2.0)    # no further page
    h.touch(FILE_LIST, 0x0a, settle=6.0)    # previous page
    h.touch(FILE_LIST, 0x02, settle=4.0)    # [d] models
    h.touch(FILE_LIST, 0x01, settle=4.0)    # [d] deep
    h.touch(FILE_LIST, 0x00, settle=4.0)    # back
    h.touch(FILE_LIST, 0x00, settle=6.0)    # back to the root
    h.touch(FILE_LIST, 0x0d, settle=4.0)    # USB
    h.touch(FILE_LIST, 0x0b, settle=3.0)    # next page on USB
    h.touch(FILE_LIST, 0x0a, settle=3.0)
    h.touch(FILE_LIST, 0x00, settle=2.0)    # back on the USB root does nothing
    h.touch(FILE_LIST, 0x0c, settle=6.0)    # local
    h.mark("preview")
    h.touch(FILE_LIST, 0x03, settle=1.0)    # [f] Benchy PLA.gcode
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, 0x02, settle=1.0)      # bed levelling switch
    h.touch(PREVIEW, 0x02, settle=1.0)
    h.touch(PREVIEW, 0x00, settle=6.0)      # back
    h.wait_page(FILE_LIST)
    h.mark("cache")
    h.touch(FILE_LIST, 0x00, settle=1.0)    # the first file
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, ALL_TO_MAIN, settle=3.0)
    h.wait_page(MAIN)
    h.touch(MAIN, 0x06, settle=1.0)         # cache button on the main page
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, ALL_TO_ADJUST, settle=2.0)
    h.mark("jpg thumbnail")
    h.touch(FILAMENT, ALL_TO_FILE_LIST, settle=6.0)
    h.touch(FILE_LIST, 0x0b, settle=5.0)    # page 2
    h.touch(FILE_LIST, 0x02, settle=1.0)    # [f] part_abs.gcode (160x160 jpg thumbnail, 300px metadata)
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, 0x00, settle=6.0)
    h.touch(FILE_LIST, 0x03, settle=1.0)    # [f] z_last.gcode (no picture)
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, ALL_TO_SETTING, settle=2.0)
    h.settle(2.0)


def _start_print(h, button, filename):
    h.touch(MAIN, ALL_TO_FILE_LIST, settle=1.0)
    h.wait_page(FILE_LIST)
    h.settle(6.0)
    h.touch(FILE_LIST, button, settle=1.0)
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, 0x01, settle=3.0)      # start
    h.mr.push_status({"print_stats": {"state": "printing", "filename": filename, "print_duration": 1.0},
                      "idle_timeout": {"state": "Printing"}})
    h.settle(2.0)


def scenario_print_flow(h):
    """Start a print from the file list, printing pages, pause / resume, z-offset, stop."""
    boot(h)
    h.touch(MAIN, ALL_TO_FILE_LIST, settle=1.0)
    h.wait_page(FILE_LIST)
    h.settle(6.0)
    h.touch(FILE_LIST, 0x0b, settle=5.0)    # page 2
    h.touch(FILE_LIST, 0x01, settle=1.0)    # cube.gcode (PLA)
    h.wait_page(PREVIEW)
    wait_preview_loaded(h)
    h.touch(PREVIEW, 0x01, settle=3.0)      # start
    h.wait_page(PREVIEW_POP_1)
    h.mr.push_status({"print_stats": {"state": "printing", "filename": "cube.gcode", "print_duration": 1.0},
                      "idle_timeout": {"state": "Printing"}})
    h.settle(1.5)
    h.touch(PREVIEW_POP_1, 0x01, settle=1.5)    # don't show again -> printing
    h.wait_page(PRINTING)
    h.mr.push_status({"display_status": {"progress": 0.05}, "print_stats": {"print_duration": 125.4},
                      "extruder": {"temperature": 219.6, "target": 220.0},
                      "heater_bed": {"temperature": 59.5, "target": 60.0},
                      "fan_generic cooling_fan": {"speed": 0.47}, "output_pin caselight": {"value": 1.0}})
    h.settle(1.5)
    # NOTE: progress and duration are pushed separately: the parse thread updates
    # them one after the other and the refresh thread of both implementations may
    # (or may not) show the half-updated state, which made the trace racy.
    h.mr.push_status({"print_stats": {"print_duration": 2500.0}})
    h.settle(1.5)
    h.mr.push_status({"display_status": {"progress": 0.4567}})
    h.settle(1.5)
    h.touch(PRINTING, 0x03, settle=1.0)     # LED
    h.touch(PRINTING, 0x00, settle=1.0)     # keyboard opened
    with h.other_page_events():             # the virtual screen shows the stop page here
        h.set_number(PRINTING, 0x00, 230, settle=1.0)
    h.touch(PRINTING, 0x02, settle=1.5)     # next
    h.wait_page(PRINTING_2)
    h.mr.push_status({"gcode_move": {"speed_factor": 1.25, "extrude_factor": 0.95,
                                     "homing_origin": [0.0, 0.0, -0.0123, 0.0]}})
    h.settle(1.5)
    h.touch(PRINTING_2, 0x01, settle=1.5)   # z-offset page
    h.wait_page(PRINT_ZOFFSET)
    for w in (0x02, 0x03, 0x04, 0x01):
        h.touch(PRINT_ZOFFSET, w, settle=1.0)
    h.touch(PRINT_ZOFFSET, 0x05, settle=1.0)
    h.touch(PRINT_ZOFFSET, 0x06, settle=1.0)
    h.mr.push_status({"gcode_move": {"homing_origin": [0.0, 0.0, 0.05, 0.0], "gcode_position": [0.0, 0.0, 1.2345, 0.0]}})
    h.settle(2.0)
    h.touch(PRINT_ZOFFSET, 0x00, settle=1.5)
    h.touch(PRINTING_2, 0x00, settle=1.5)
    h.wait_page(PRINTING)
    h.mark("pause")
    h.touch(PRINTING, 0x0a, settle=1.5)     # pause
    h.wait_page(PRINT_FILAMENT)
    h.mr.push_status({"print_stats": {"state": "paused"}, "pause_resume": {"is_paused": True}})
    h.settle(2.0)
    h.touch(PRINT_FILAMENT, 0x0a, settle=1.0)   # resume
    h.mr.push_status({"print_stats": {"state": "printing"}, "pause_resume": {"is_paused": False}})
    h.settle(2.0)
    h.wait_page(PRINTING)
    h.mark("stop")
    h.touch(PRINTING, 0x0b, settle=1.5)
    h.wait_page(PRINT_STOP)
    h.touch(PRINT_STOP, 0x01, settle=1.5)   # no
    h.wait_page(PRINTING)
    h.touch(PRINTING, 0x0b, settle=1.5)
    h.touch(PRINT_STOP, 0x00, settle=2.0)   # yes -> cancel
    h.wait_page(PRINT_STOPPING)
    h.mr.push_status({"print_stats": {"state": "cancelled", "filename": ""}, "idle_timeout": {"state": "Ready"}})
    h.settle(4.0)
    h.wait_page(MAIN)
    h.settle(3.0)
    h.mark("complete")
    _start_print(h, 0x03, "Benchy PLA.gcode")
    h.wait_page(PREVIEW_POP_2)                   # filament_name "Generic ABS"
    h.touch(PREVIEW_POP_2, 0x00, settle=1.5)
    h.wait_page(PRINTING)
    h.mr.push_status({"print_stats": {"print_duration": 3725.9}})
    h.settle(1.5)
    h.mr.push_status({"display_status": {"progress": 1.0}})
    h.settle(1.5)
    h.mr.push_status({"print_stats": {"state": "complete"}})
    h.settle(5.0)
    h.wait_page(PRINT_FINISH)
    h.touch(PRINT_FINISH, 0x00, settle=2.0)
    h.wait_page(MAIN)
    h.settle(3.0)


def scenario_print_events(h):
    """Print started from the web UI, filament runout, filament page while paused, errors."""
    boot(h)
    h.mr.push_status({"print_stats": {"state": "printing", "filename": "part_abs.gcode", "print_duration": 5.0},
                      "idle_timeout": {"state": "Printing"}})
    h.wait_page(PREVIEW, 20)
    h.wait_page(PREVIEW_POP_2, 40)
    h.touch(PREVIEW_POP_2, 0x00, settle=1.5)
    h.wait_page(PRINTING)
    h.mr.push_status({"display_status": {"progress": 0.12}, "print_stats": {"print_duration": 61.0}})
    h.settle(1.5)
    h.mark("runout")
    h.mr.push_status({"filament_switch_sensor fila": {"filament_detected": False}})
    h.settle(2.0)
    h.wait_page(PRINT_NO_FILAMENT_2)
    h.mr.push_status({"filament_switch_sensor fila": {"filament_detected": True},
                      "print_stats": {"state": "paused"}})
    h.settle(1.5)
    h.touch(PRINT_NO_FILAMENT_2, 0x00, settle=2.0)   # falls through into the low temperature case
    h.wait_page(PRINT_FILAMENT)
    h.touch(PRINT_FILAMENT, 0x01, settle=1.0)
    h.touch(PRINT_FILAMENT, 0x02, settle=1.0)
    h.touch(PRINT_FILAMENT, 0x00, settle=1.0)
    h.touch(PRINT_FILAMENT, 0x05, settle=1.0)       # retract (M603)
    h.touch(PRINT_FILAMENT, 0x06, settle=1.0)       # extrude
    h.mr.push_gcode("!! Extrude below minimum temp")
    h.settle(2.0)
    h.wait_page(PRINT_LOW_TEMP)
    h.touch(PRINT_LOW_TEMP, 0x00, settle=1.5)
    h.wait_page(PRINT_FILAMENT)
    h.touch(PRINT_FILAMENT, 0x03, settle=1.0)       # load -> pre heat
    h.wait_page(PRE_HEAT)
    h.touch(PRE_HEAT, 0x04, settle=1.5)             # back (paused -> print filament)
    h.wait_page(PRINT_FILAMENT)
    h.mark("hall")
    h.mr.push_gcode("// Filament dia (measured mm): 0.12")
    h.settle(3.0)
    h.wait_page(PRINT_NO_FILAMENT)
    h.mr.push_gcode("// Filament dia (measured mm): 1.75")
    h.settle(1.0)
    h.touch(PRINT_NO_FILAMENT, 0x00, settle=1.5)
    h.mr.push_status({"print_stats": {"state": "printing"}})
    h.settle(2.0)
    h.mark("error")
    h.mr.push_gcode("!! Heater extruder not heating at expected rate")
    h.settle(1.5)
    h.mr.push_status({"print_stats": {"state": "error", "message": "boom"}})
    h.settle(3.0)
    h.wait_page(GCODE_ERROR)
    h.touch(GCODE_ERROR, 0x00, settle=1.5)
    h.mr.push_status({"print_stats": {"state": "standby", "filename": ""}})
    h.settle(2.0)


def scenario_temperatures(h):
    """Filament / temperature page: keyboards, heaters, fans, distances."""
    boot(h)
    h.touch(MAIN, 0x03, settle=1.5)     # set temperatures -> filament page
    h.wait_page(FILAMENT)
    h.touch(FILAMENT, 0x00, settle=1.0)
    h.wait_page(FILAMENT_KB)
    h.set_number(FILAMENT, 0x00, 250, settle=1.5)
    h.set_number(FILAMENT, 0x01, 130, settle=1.5)    # capped at 120
    h.set_number(FILAMENT, 0x10, 70, settle=1.5)     # capped at 60
    h.set_number(FILAMENT, 0x00, 0, settle=1.5)      # 0 is not stored in the ini
    h.mr.push_status({"extruder": {"target": 250.0}, "heater_bed": {"target": 120.0},
                      "heater_generic chamber": {"target": 60.0}})
    h.settle(1.5)
    for w in (0x02, 0x03, 0x0f):
        h.touch(FILAMENT, w, settle=1.0)
    h.mr.push_status({"extruder": {"target": 0.0}, "heater_bed": {"target": 0.0},
                      "heater_generic chamber": {"target": 0.0}})
    h.settle(1.5)
    for w in (0x02, 0x03, 0x0f):
        h.touch(FILAMENT, w, settle=1.0)
    for w in (0x09, 0x0b, 0x0a):
        h.touch(FILAMENT, w, settle=1.0)
    h.touch(FILAMENT, 0x07, settle=1.0)     # retract
    h.touch(FILAMENT, 0x08, settle=1.0)     # extrude
    h.mr.push_status({"fan_generic cooling_fan": {"speed": 0.3}, "fan_generic auxiliary_cooling_fan": {"speed": 0.555},
                      "fan_generic chamber_circulation_fan": {"speed": 1.0}})
    h.settle(1.5)
    for tile, fan, value in ((0x11, 0x0c, 80), (0x12, 0x0d, 255), (0x13, 0x0e, 33)):    # the fan tiles open the number keyboard
        h.touch(FILAMENT, tile, settle=1.0)
        h.wait_page(FILAMENT_KB)
        h.set_number(FILAMENT, fan, value, settle=1.0)
        h.wait_page(FILAMENT)
    h.mr.push_status({"fan_generic cooling_fan": {"speed": 0.8}})
    h.settle(1.5)
    h.mark("printing keyboard")
    with h.other_page_events():             # the virtual screen shows the filament page here
        for w, v in ((0x00, 400), (0x01, 70), (0x04, 120), (0x05, 50), (0x06, 7), (0x02, 200), (0x03, 99), (0x07, 61)):
            h.set_number(PRINTING, w, v, settle=1.0)
    h.touch(FILAMENT, ALL_TO_SETTING, settle=1.5)
    h.wait_page(LEVEL_MODE)
    h.touch(LEVEL_MODE, ALL_TO_ADJUST, settle=1.5)
    h.wait_page(FILAMENT)
    h.settle(1.0)


def scenario_move_page(h):
    """Move page, homing pop-ups and errors."""
    boot(h)
    h.touch(MAIN, ALL_TO_ADJUST, settle=1.5)
    h.wait_page(FILAMENT)
    h.touch(FILAMENT, 0x17, settle=1.5)
    h.wait_page(MOVE)
    for w in (0x00, 0x01, 0x02):
        h.touch(MOVE, w, settle=1.0)
    for w in (0x09, 0x08, 0x06, 0x07, 0x03, 0x05):
        h.touch(MOVE, w, settle=1.0)
    h.touch(MOVE, 0x00, settle=1.0)
    h.touch(MOVE, 0x09, settle=1.0)
    h.mr.push_status({"toolhead": {"position": [12.345, 200.06, 5.55, 1.0]}})
    h.settle(1.5)
    h.mr.push_status({"toolhead": {"position": [-1.25, 0.05, 249.99, 1.0]}})
    h.settle(1.5)
    h.touch(MOVE, 0x0a, settle=1.0)     # home
    h.touch(MOVE, 0x04, settle=1.0)     # motors off
    h.mark("unhomed")
    h.touch(MOVE, 0x07, settle=1.0)
    h.mr.push_gcode("!! Must home axis first: 125.000 125.000 10.000 [0.000]")
    h.settle(2.0)
    h.wait_page(MOVE_POP_2)
    h.touch(MOVE_POP_2, 0x01, settle=1.5)
    h.touch(MOVE, 0x05, settle=1.0)
    h.mr.push_gcode("!! Must home axis first: 125.000 125.000 10.000 [0.000]")
    h.settle(2.0)
    h.touch(MOVE_POP_2, 0x00, settle=1.5)   # yes -> home
    h.mr.push_gcode("!! Move out of range: 300.000 125.000 10.000 [0.000]")
    h.settle(2.0)
    h.wait_page(MOVE_POP_1)
    h.touch(MOVE_POP_1, 0x00, settle=1.5)
    h.wait_page(MOVE)
    h.mr.push_gcode("!! Extrude below minimum temp")
    h.settle(2.0)
    h.wait_page(FILAMENT_POP_1)
    h.touch(FILAMENT_POP_1, 0x00, settle=1.5)
    h.wait_page(FILAMENT)
    h.touch(FILAMENT, 0x17, settle=1.5)
    h.touch(MOVE, 0x16, settle=1.5)     # to filament
    h.touch(FILAMENT, ALL_TO_MAIN, settle=1.5)
    h.touch(MAIN, ALL_TO_ADJUST, settle=1.5)
    h.settle(1.0)


def scenario_levelling(h):
    """Z-offset table, automatic levelling, input shaping, probe results."""
    boot(h)
    h.touch(MAIN, ALL_TO_SETTING, settle=1.5)
    h.wait_page(LEVEL_MODE)
    h.touch(LEVEL_MODE, 0x18, settle=2.0)   # mesh values
    h.wait_page(ZOFFSET)
    h.touch(ZOFFSET, 0x00, settle=1.5)
    h.touch(LEVEL_MODE, 0x00, settle=1.5)   # auto levelling
    h.wait_page(AUTO_HEATERBED)
    h.touch(AUTO_HEATERBED, 0x01, settle=1.0)
    h.touch(AUTO_HEATERBED, 0x00, settle=1.0)
    h.touch(AUTO_HEATERBED, 0x02, settle=1.0)
    h.touch(AUTO_HEATERBED, 0x04, settle=1.5)   # target < 35 -> warning
    h.wait_page(AUTO_WARNING)
    h.touch(AUTO_WARNING, 0x00, settle=1.0)
    h.mr.push_status({"heater_bed": {"target": 60.0, "temperature": 40.3}})
    h.settle(1.5)
    h.touch(AUTO_HEATERBED, 0x04, settle=1.5)   # start
    h.wait_page(AUTO_MOVING)
    h.mr.push_gcode("// action:librescreen homed")
    h.settle(1.5)
    h.mr.push_gcode("// action:librescreen nozzle_cleared")
    h.settle(1.5)
    h.mr.push_gcode("// action:librescreen nozzle_cooled")
    h.settle(2.5)
    h.mr.push_gcode("// action:librescreen bed_mesh_done")
    h.settle(6.0)
    h.wait_page(AUTO_FINISH)
    h.touch(AUTO_FINISH, 0x00, settle=1.5)
    h.wait_page(LEVEL_MODE)
    h.mark("syntony")
    h.touch(LEVEL_MODE, 0x01, settle=1.5)
    h.wait_page(SYNTONY_MOVE)
    h.mr.push_gcode("// Recommended shaper_type_x = mzv, shaper_freq_x = 52.4 Hz")
    h.settle(1.0)
    h.mr.push_gcode("// Recommended shaper_type_y = ei, shaper_freq_y = 41.2 Hz")
    h.settle(1.0)
    h.mr.push_gcode("// PID parameters: pid_Kp=22.2 pid_Ki=1.08 pid_Kd=114")
    h.settle(1.0)
    h.mr.push_gcode("// Z position: 0.100 -> 0.125 <- 0.150")
    h.settle(1.0)
    h.mr.push_gcode("// action:librescreen input_shaping_done")
    h.settle(6.0)
    h.wait_page(SYNTONY_FINISH)
    h.touch(SYNTONY_FINISH, 0x00, settle=2.0)
    h.wait_page(LEVEL_MODE)
    h.touch(LEVEL_MODE, 0x01, settle=1.5)
    h.touch(SYNTONY_MOVE, 0x00, settle=2.0)     # jump out
    h.settle(1.0)


def scenario_bed_calibration(h):
    """Manual bed screw calibration sequence."""
    boot(h)
    h.touch(MAIN, ALL_TO_SETTING, settle=1.5)
    h.touch(LEVEL_MODE, 0x02, settle=1.5)
    h.wait_page(CALIBRATE_WARNING)
    h.touch(CALIBRATE_WARNING, 0x01, settle=1.5)
    h.touch(LEVEL_MODE, 0x02, settle=1.5)
    h.touch(CALIBRATE_WARNING, 0x00, settle=1.5)    # manual_count = 4
    h.wait_page(BED_MOVING)
    h.mr.push_status({"idle_timeout": {"state": "Ready"}})
    h.settle(2.0)
    h.wait_page(PRE_BED_CALIBRATION)
    for w in (0x00, 0x01, 0x02, 0x03):
        h.touch(PRE_BED_CALIBRATION, w, settle=1.0)
    h.touch(PRE_BED_CALIBRATION, 0x02, settle=1.0)
    h.touch(PRE_BED_CALIBRATION, 0x04, settle=1.0)
    h.touch(PRE_BED_CALIBRATION, 0x04, settle=1.0)
    h.touch(PRE_BED_CALIBRATION, 0x05, settle=1.0)
    h.touch(PRE_BED_CALIBRATION, 0x06, settle=1.5)  # enter (manual_count 3)
    for i in range(3):
        h.wait_page(BED_MOVING)
        h.mr.push_status({"idle_timeout": {"state": "Printing"}})
        h.settle(1.0)
        h.mr.push_status({"idle_timeout": {"state": "Ready"}})
        h.settle(2.0)
        h.wait_page(BED_CALIBRATION)
        h.touch(BED_CALIBRATION, 0x00, settle=1.5)
    h.wait_page(BED_FINISH)
    for w in (0x01, 0x02, 0x03, 0x04):
        h.touch(BED_FINISH, w, settle=1.5)
        h.mr.push_status({"idle_timeout": {"state": "Printing"}})
        h.settle(1.0)
        h.mr.push_status({"idle_timeout": {"state": "Ready"}})
        h.settle(2.0)
        if h.screen.page == BED_CALIBRATION:
            h.touch(BED_CALIBRATION, 0x00, settle=1.5)
        h.wait_page(BED_FINISH)
    h.touch(BED_FINISH, 0x00, settle=1.5)
    h.settle(1.0)


def scenario_settings(h):
    """Common settings: language, system info, logs, restarts, guide switch, restore."""
    boot(h)
    goto_common_setting(h)
    h.settle(1.5)
    h.touch(COMMON_SETTING, 0x00, settle=1.5)
    h.wait_page(LANGUAGE)
    h.touch(LANGUAGE, 0x00, settle=1.5)
    h.touch(COMMON_SETTING, 0x02, settle=1.5)    # system
    h.wait_page(SYS_OK)
    h.touch(SYS_OK, 0x01, settle=3.0)            # export logs to USB
    h.wait_page(PRINT_LOG_S)
    h.touch(PRINT_LOG_S, 0x00, settle=1.5)
    h.wait_page(SYS_OK)
    h.touch(SYS_OK, 0x02, settle=1.0)            # restart klipper
    h.touch(SYS_OK, 0x03, settle=1.0)            # restart firmware
    h.touch(SYS_OK, 0x00, settle=1.5)
    h.touch(COMMON_SETTING, 0x04, settle=1.5)    # sleep mode
    h.touch(SLEEP_MODE, 0x00, settle=1.5)
    h.touch(COMMON_SETTING, 0x17, settle=2.0)    # guide on
    h.touch(COMMON_SETTING, 0x07, settle=2.0)    # guide off
    h.touch(COMMON_SETTING, 0x06, settle=1.5)    # restore
    h.wait_page(RESTORE_CONFIG)
    h.touch(RESTORE_CONFIG, 0x01, settle=1.5)
    h.touch(COMMON_SETTING, 0x06, settle=1.5)
    h.touch(RESTORE_CONFIG, 0x00, settle=3.0)    # yes
    h.wait_page(MAIN)
    h.settle(4.0)
    h.touch(MAIN, ALL_TO_SETTING, settle=1.5)
    h.touch(COMMON_SETTING, 0x16, settle=1.5)
    h.settle(1.0)


def scenario_language(h):
    """The language lives on the screen only: the port asks for it at start-up and follows a change (the network
    page texts come from the language of the screen)."""
    h.screen.lang = 1                           # Russian, stored in the EEPROM of the screen
    boot(h)
    h.mark("russian")
    goto_common_setting(h)
    h.touch(COMMON_SETTING, 0x01, settle=1.5)   # network: the network info is the first page
    h.wait_page(NET_INFO)
    h.touch(NET_INFO, 0x02, settle=1.5)         # the list of Wi-Fi networks
    h.wait_page(WIFI_LIST)
    h.touch(WIFI_LIST, 0x08, settle=1.5)        # saved networks
    h.wait_page(NET_SAVED)
    h.mark("japanese")
    h.screen.set_language(3)                    # picked on the language page
    h.settle(1.0)
    h.touch(NET_SAVED, 23, settle=1.5)          # back to the list
    h.wait_page(WIFI_LIST)
    h.touch(WIFI_LIST, 0x17, settle=1.5)        # back to the network info
    h.wait_page(NET_INFO)
    h.touch(NET_INFO, 23, settle=1.5)           # back to the settings
    h.touch(COMMON_SETTING, 0x01, settle=1.5)
    h.touch(NET_INFO, 0x02, settle=1.5)
    h.touch(WIFI_LIST, 0x08, settle=1.5)
    h.wait_page(NET_SAVED)
    h.settle(1.0)


def scenario_errors(h):
    """Klipper shutdown / ready, gcode errors, Klipper state messages."""
    boot(h)
    h.mr.push_status({"webhooks": {"state": "shutdown",
                                   "state_message": "MCU 'mcu' shutdown: Timer too close\nOnce the underlying issue is corrected, use the \"FIRMWARE_RESTART\" command"}})
    h.settle(2.0)
    h.wait_page(RESET)
    h.touch(RESET, ALL_TO_MAIN, settle=1.0)      # ignored in error state
    h.touch(RESET, 0x00, settle=1.5)             # common settings
    h.touch(COMMON_SETTING, 0x02, settle=1.5)    # go_to_reset in shutdown state
    h.mr.push_status({"webhooks": {"state": "error", "state_message": "Klipper reports: ERROR 'x'"}})
    h.settle(2.0)
    h.mr.push_status({"webhooks": {"state": "ready", "state_message": "Printer is ready"}})
    h.settle(2.0)
    h.wait_page(SYS_OK)
    h.touch(SYS_OK, ALL_TO_MAIN, settle=2.0)
    h.wait_page(MAIN)
    h.mark("gcode errors")
    h.mr.push_gcode("!! Unknown command:\"FOO\"")
    h.settle(2.0)
    h.wait_page(DETECT_ERROR)
    h.touch(DETECT_ERROR, 0x00, settle=2.0)
    h.mr.push_gcode("!! Printer is not ready")
    h.settle(1.0)
    h.mr.push_gcode("!! Can not update MCU 'mcu' config as it is shutdown")
    h.settle(1.0)
    h.mr.push_gcode("!! Insufficient disk space, unable to read the file.")
    h.settle(2.0)
    h.wait_page(MEMORY_WARNING)
    h.touch(MEMORY_WARNING, 0x00, settle=1.5)
    h.mr.push_gcode("// Klipper state: Disconnect")
    h.settle(1.5)
    h.mr.push_gcode("// Klipper state: Ready")
    h.settle(5.0)
    h.mr.push_gcode("// action:cancel")
    h.settle(1.0)
    h.mr.push_gcode("Result is z=0.123")
    h.settle(1.0)
    h.touch(MAIN, ALL_TO_SETTING, settle=1.5)
    h.touch(LEVEL_MODE, 0x00, settle=1.5)
    h.mr.push_status({"heater_bed": {"target": 60.0}})
    h.settle(1.0)
    h.touch(AUTO_HEATERBED, 0x04, settle=1.5)
    h.wait_page(AUTO_MOVING)
    h.mr.push_gcode("!! Probe triggered prior to movement")
    h.settle(2.0)
    h.wait_page(LEVEL_ERROR)
    h.touch(LEVEL_ERROR, 0x00, settle=1.5)
    h.settle(1.0)


def scenario_notifications(h):
    """Moonraker notifications, error responses and the history notification."""
    boot(h)
    for method in ("notify_proc_stat_update", "notify_klippy_shutdown", "notify_update_response",
                   "notify_update_refreshed", "notify_cpu_throttled", "notify_user_created",
                   "notify_user_deleted", "notify_service_state_changed", "notify_job_queue_changed",
                   "notify_button_event", "notify_announcement_update", "notify_announcement_dismissed",
                   "notify_announcement_wake", "notify_agent_event", "notify_power_changed",
                   "notify_unknown_thing"):
        h.mr.notify(method, [{}])
    h.mr.drain()
    h.mr.notify("notify_klippy_ready")
    h.settle(1.5)
    h.mr.notify("notify_klippy_disconnected")
    h.settle(1.5)
    h.mr.notify("notify_filelist_changed", [{"action": "create_file", "item": {"path": "x.gcode"}}])
    h.settle(1.0)
    h.mr.notify("notify_history_changed", [{"action": "added", "job": {
        "metadata": {"estimated_time": 4000.7, "filename": "dir/web_print.gcode", "filament_total": 333.3,
                     "filament_weight_total": 1.25, "filament_type": "PETG", "object_height": 12.5,
                     "gimage": "", "simage": ""}}}])
    h.settle(1.0)
    h.mr.push_raw(json.dumps({"jsonrpc": "2.0", "error": {"code": 400, "message": "bad"}, "id": 1}))
    h.settle(1.0)
    h.mr.push_raw(json.dumps({"jsonrpc": "2.0", "result": {"software_version": "v9"}, "id": 5445}))
    h.settle(1.0)
    h.mr.push_raw(json.dumps({"jsonrpc": "2.0", "result": {"job_totals": {"total_print_time": 77.5}}, "id": 5656}))
    h.settle(1.0)
    h.mr.push_raw(json.dumps({"jsonrpc": "2.0", "result": "ok", "id": 4654}))
    h.settle(1.0)
    h.mr.push_raw(json.dumps({"jsonrpc": "2.0", "result": {"status": {"extruder": {"temperature": 99.9}}}, "id": 4654}))
    h.settle(2.0)
    h.mark("invalid_json")
    # invalid JSON is logged and ignored (the C++ code died with std::terminate)
    h.mr.push_raw("{not json")
    h.settle(3.0)


def scenario_screen_sleep(h):
    """Screen sleep with the LED on, wake up by a gcode response and by touch."""
    boot(h)
    h.mr.push_status({"output_pin caselight": {"value": 1.0}})
    h.settle(1.5)
    h.touch(SCREEN_SLEEP, 0x01, settle=1.5)     # enter
    h.mr.push_status({"output_pin caselight": {"value": 0.0}})
    h.settle(1.0)
    h.mr.push_gcode("// some gcode response")
    h.settle(2.0)
    h.mr.push_status({"output_pin caselight": {"value": 1.0}})
    h.settle(1.0)
    h.touch(SCREEN_SLEEP, 0x01, settle=1.5)
    h.mr.push_status({"output_pin caselight": {"value": 0.0}})
    h.settle(1.0)
    h.touch(SCREEN_SLEEP, 0x00, settle=2.0)     # exit
    h.touch(MAIN, ALL_TO_FILE_LIST, settle=4.0)
    h.touch(SCREEN_SLEEP, 0x01, settle=1.5)
    h.touch(SCREEN_SLEEP, 0x00, settle=5.0)     # exit to the file list
    h.settle(1.0)


def scenario_filament(h):
    """Filament load / unload (automatic and manual)."""
    boot(h)
    h.touch(MAIN, 0x03, settle=1.5)
    h.wait_page(FILAMENT)
    h.touch(FILAMENT, 0x05, settle=1.5)         # load
    h.wait_page(PRE_HEAT)
    h.touch(PRE_HEAT, 0x01, settle=1.5)         # 250
    h.wait_page(FILAMENT_POP_3)
    h.touch(FILAMENT_POP_3, 0x02, settle=1.5)   # next -> filament_load()
    h.mr.push_status({"extruder": {"temperature": 249.6, "target": 250.0}})
    h.settle(1.0)
    h.mr.push_gcode("// action:librescreen filament_heated")
    h.settle(1.5)
    h.mr.push_gcode("// action:librescreen filament_loaded")
    h.settle(1.0)
    h.mr.push_status({"idle_timeout": {"state": "Ready"}})
    h.settle(1.5)
    h.touch(FILAMENT_POP_3, 0x01, settle=1.5)   # retry
    h.touch(FILAMENT_POP_3, 0x03, settle=1.5)   # back -> pre heat
    h.touch(PRE_HEAT, 0x02, settle=1.5)         # 300
    h.touch(FILAMENT_POP_3, 0x00, settle=1.5)   # done
    h.wait_page(FILAMENT)
    h.mark("unload")
    h.touch(FILAMENT, 0x06, settle=1.5)
    h.touch(PRE_HEAT, 0x00, settle=1.5)         # 220 -> unload mode
    h.wait_page(UNLOAD_MODE)
    h.touch(UNLOAD_MODE, 0x01, settle=1.5)      # automatic
    h.wait_page(AUTO_UNLOAD)
    h.mr.push_gcode("// action:librescreen filament_heated")
    h.settle(1.5)
    h.mr.push_gcode("// action:librescreen filament_unloaded")
    h.settle(1.5)
    h.touch(AUTO_UNLOAD, 0x00, settle=1.5)      # to load
    h.touch(PRE_HEAT, 0x04, settle=1.5)         # back
    h.touch(FILAMENT, 0x06, settle=1.5)
    h.touch(PRE_HEAT, 0x00, settle=1.5)
    h.touch(UNLOAD_MODE, 0x00, settle=1.5)      # manual
    h.wait_page(FILAMENT_POP_2)
    h.touch(FILAMENT_POP_2, 0x02, settle=1.5)   # next -> load
    h.mr.push_gcode("// action:librescreen filament_heated")
    h.settle(1.5)
    h.touch(FILAMENT_POP_2, 0x01, settle=1.5)   # to load
    h.touch(PRE_HEAT, 0x04, settle=1.5)
    h.touch(FILAMENT, 0x06, settle=1.5)
    h.touch(PRE_HEAT, 0x00, settle=1.5)
    h.touch(UNLOAD_MODE, 0x00, settle=1.5)
    h.touch(FILAMENT_POP_2, 0x03, settle=1.5)   # back -> unload mode
    h.touch(UNLOAD_MODE, 0x02, settle=1.5)      # back -> pre heat
    h.touch(PRE_HEAT, 0x04, settle=1.5)
    h.touch(FILAMENT, 0x06, settle=1.5)
    h.touch(PRE_HEAT, 0x00, settle=1.5)
    h.touch(UNLOAD_MODE, 0x00, settle=1.5)
    h.touch(FILAMENT_POP_2, 0x00, settle=1.5)   # done
    h.mr.push_gcode("// Filament NOT present")
    h.settle(1.0)
    h.mr.push_gcode("// action:librescreen filament_runout")
    h.settle(1.0)
    h.settle(1.0)


