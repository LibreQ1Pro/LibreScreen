"""Heaters, fans, speed and flow, and the LED / beeper switches."""

import logging
import sys

from librescreen import state as g
from librescreen.config import settings
from librescreen.moonraker.gcodes import set_fan0_speed, set_fan2_speed, set_fan3_speed, set_heater_temp, set_speed_rate
from librescreen.screen import pageids as ids
from librescreen.util.cpp import to_string

log = logging.getLogger(__name__)


def set_target(heater, target):
    # info level on purpose: "the nozzle heats to a temperature nobody chose" needs to show who asked (the caller two frames up)
    log.info("%s target %s (asked by %s)", heater, target, sys._getframe(2).f_code.co_name)
    g.ep.run_gcode(set_heater_temp(heater, target))


def set_extruder_target(target):
    set_target("extruder", target)


def set_heater_bed_target(target):
    set_target("heater_bed", target)


def set_hot_target(target):
    g.ep.run_gcode("M141 S" + to_string(target))


def set_fan0(speed):
    g.ep.run_gcode(set_fan0_speed(speed))


def set_fan2(speed):
    g.ep.run_gcode(set_fan2_speed(speed))


def set_fan3(speed):
    g.ep.run_gcode(set_fan3_speed(speed))


def set_printer_speed(speed):
    log.debug("Rate = %s", to_string(speed))
    g.ep.run_gcode(set_speed_rate(to_string(speed)))


def set_printer_flow(rate):
    g.ep.run_gcode("M221 S" + to_string(rate))


def set_filament_extruder_target(positive):
    settings.get_extruder_target()
    g.klippy.filament_extruder_target = g.config.extruder_target
    log.debug("filament target %s: saved %s, set now %s", "+3" if positive else "-3", g.config.extruder_target, g.klippy.extruder_target)
    if positive:
        g.klippy.filament_extruder_target += 3
    else:
        g.klippy.filament_extruder_target -= 3

    if g.klippy.filament_extruder_target >= 350:
        g.klippy.filament_extruder_target = 350

    if g.klippy.filament_extruder_target < 0:
        g.klippy.filament_extruder_target = 0
        set_extruder_target(0)
        settings.set_extruder_target(0)
    else:
        set_extruder_target(g.klippy.filament_extruder_target)
        settings.set_extruder_target(g.klippy.filament_extruder_target)


def beep_on_off():
    g.ep.run_gcode("beep_off" if g.klippy.out_pin_beep_value else "beep_on")


def led_on_off():
    g.ep.run_gcode("light_off" if g.klippy.caselight_value else "light_on")


def filament_extruder_target():
    settings.get_extruder_target()
    if g.klippy.extruder_target == 0:
        set_extruder_target(g.config.extruder_target)
    else:
        set_extruder_target(0)


def filament_heater_bed_target():
    settings.get_heater_bed_target()
    if 0 == g.klippy.heater_bed_target:
        set_heater_bed_target(g.config.heater_bed_target)
    else:
        set_heater_bed_target(0)


def filament_hot_target():
    settings.get_hot_target()
    if 0 == g.klippy.hot_target:
        set_hot_target(g.config.hot_target)
    else:
        set_hot_target(0)


def set_print_filament_target():
    if 0 == g.klippy.extruder_target:
        settings.get_extruder_target()
        set_extruder_target(g.config.extruder_target)
    else:
        set_extruder_target(0)


def open_set_print_filament_target():
    if 0 == g.klippy.extruder_target:
        settings.get_extruder_target()
        set_extruder_target(g.config.extruder_target)
    else:
        set_extruder_target(0)


def set_auto_level_heater_bed_target(positive):
    settings.get_heater_bed_target()
    g.levelling.auto_level_heater_bed_target = g.config.heater_bed_target
    if positive:
        g.levelling.auto_level_heater_bed_target += 3
    else:
        g.levelling.auto_level_heater_bed_target -= 3
    if g.levelling.auto_level_heater_bed_target > 120:
        g.levelling.auto_level_heater_bed_target = 120
    if g.levelling.auto_level_heater_bed_target < 0:
        g.levelling.auto_level_heater_bed_target = 0
    set_heater_bed_target(g.levelling.auto_level_heater_bed_target)
    settings.set_heater_bed_target(g.levelling.auto_level_heater_bed_target)
