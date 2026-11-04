"""Gcode builders (heater, fan, speed and relative moves)."""

import logging

from librescreen.moonraker.rpc_requests import json_run_a_gcode
from librescreen.util.cpp import f32, to_string

log = logging.getLogger(__name__)

AXIS_X = "X"
AXIS_Y = "Y"
AXIS_Z = "Z"

HOME = "G28"
HOME_X = "G28 X"
HOME_Y = "G28 Y"
HOME_Z = "G28 Z"
HOME_XY = "G28 X Y"
Z_TILT = "Z_TILT_ADJUST"
QUAD_GANTRY_LEVEL = "QUAD_GANTRY_LEVEL"

MOVE = "G1"
MOVE_ABSOLUTE = "G90"
MOVE_RELATIVE = "G91"

EXTRUDE_ABS = "M82"
EXTRUDE_REL = "M83"

SET_EXT_TEMP = "M104"
SET_BED_TEMP = "M140"

SET_EXT_FACTOR = "M221"
SET_FAN_SPEED = "M106"
SET_SPD_FACTOR = "M220"

PROBE_CALIBRATE = "PROBE_CALIBRATE"
Z_ENDSTOP_CALIBRATE = "Z_ENDSTOP_CALIBRATE"
TESTZ = "TESTZ Z="
ABORT = "ABORT"
ACCEPT = "ACCEPT"

SAVE_CONFIG = "SAVE_CONFIG"
RESTART = "RESTART"


def set_heater_temp(heater, temp):
    return "SET_HEATER_TEMPERATURE heater=" + heater + " target=" + to_string(temp)


# Librescreen
def set_fan0_speed(speed):
    speed_temp = to_string(f32(f32(speed * 255) / 100))
    log.debug("%s", speed_temp)
    return "M106 P0 S" + speed_temp


def set_fan2_speed(speed):
    speed_temp = to_string(f32(f32(speed * 255) / 100))
    return "M106 P2 S" + speed_temp


def set_fan3_speed(speed):
    speed_temp = to_string(f32(f32(speed * 255) / 100))
    return "M106 P3 S" + speed_temp
# Librescreen


def set_speed_rate(rate):
    return SET_SPD_FACTOR + " S" + rate


def move_relative(axis, dist, speed):
    """Relative move.

    axis:  AXIS_X, AXIS_Y or AXIS_Z
    dist:  distance with direction, e.g. "+10", "-100"
    speed: speed in mm/s
    """
    return json_run_a_gcode(MOVE_RELATIVE + "\n" + MOVE + " " + axis + dist + " F" + to_string(speed * 60) + "\nG90")
