"""Parsing of the Klipper printer object status."""

import logging
import math

from librescreen import state as g
from librescreen.moonraker.json_fields import read_fields
from librescreen.util.cpp import c_int, c_round, f32, jbool, jdouble, jfloat, jget, jpath, jstr

log = logging.getLogger(__name__)


def _temperature(value):
    """Temperatures are shown rounded to whole degrees."""
    return c_int(jfloat(value) + 0.5)


def parse_server_history_totals(totals):
    read_fields(g.klippy, totals, [("total_print_time", "total_print_time", jdouble)])
    log.debug("total_print_time = %s", c_int(g.klippy.total_print_time))


def parse_printer_probe(probe):
    read_fields(g.klippy, probe, [("probe_x_zoffset", "x_offset", jfloat),
                            ("probe_y_zoffset", "y_offset", jfloat),
                            ("probe_z_zoffset", "z_offset", jfloat)])


def parse_printer_beep(beep):
    read_fields(g.klippy, beep, [("out_pin_beep_value", "enabled", jfloat)])


def parse_printer_caselight(caselight):
    read_fields(g.klippy, caselight, [("caselight_value", "value", jfloat)])


def parse_printer_heater_fan_my_nozzle_fan1(fan):
    read_fields(g.klippy, fan, [("heater_fan_my_nozzle_fan1_speed", "speed", jfloat)])


def parse_printer_out_pin_fan0(fan):
    read_fields(g.klippy, fan, [("out_pin_fan0_value", "speed", jfloat)])


def parse_printer_out_pin_fan2(fan):
    read_fields(g.klippy, fan, [("out_pin_fan2_value", "speed", jfloat)])


def parse_printer_out_pin_fan3(fan):
    read_fields(g.klippy, fan, [("out_pin_fan3_value", "speed", jfloat)])


def parse_filament_switch_sensor_fila(sensor):
    read_fields(g.klippy, sensor, [("fila_sensor_detected", "filament_detected", jbool),
                             ("fila_sensor_enabled", "enabled", jbool)])


def parse_idle_timeout(idle_timeout):
    read_fields(g.klippy, idle_timeout, [("idle_timeout_state", "state", jstr)])


def parse_bed_mesh(bed_mesh):
    levelling = g.levelling
    for key, limits in (("mesh_min", levelling.mesh_min), ("mesh_max", levelling.mesh_max)):
        if jget(bed_mesh, key) is not None:
            limits[0] = jfloat(jpath(bed_mesh, key, 0))
            limits[1] = jfloat(jpath(bed_mesh, key, 1))
    if jget(bed_mesh, "profiles") is None or jpath(bed_mesh, "profiles", "default") is None:
        return

    mesh_params = jpath(bed_mesh, "profiles", "default", "mesh_params")
    if mesh_params is not None:
        read_fields(levelling, mesh_params, [("mesh_tension", "tension", jfloat),
                                       ("mesh_mesh_x_pps", "mesh_x_pps", jfloat),
                                       ("mesh_algo", "algo", jstr),
                                       ("mesh_min_x", "min_x", jfloat),
                                       ("mesh_min_y", "min_y", jfloat),
                                       ("mesh_y_count", "y_count", jfloat),
                                       ("mesh_mesh_y_pps", "mesh_y_pps", jfloat),
                                       ("mesh_x_count", "x_count", jfloat),
                                       ("mesh_max_x", "max_x", jfloat),
                                       ("mesh_max_y", "max_y", jfloat)])

    points = jpath(bed_mesh, "profiles", "default", "points")
    if points is not None:
        # the screen shows at most 5 x 5 points
        for i in range(min(5, math.ceil(levelling.mesh_y_count))):
            for j in range(min(5, math.ceil(levelling.mesh_x_count))):
                levelling.mesh_points[i][j] = jfloat(jpath(points, i, j))


def parse_webhooks(webhooks):
    read_fields(g.klippy, webhooks, [("webhooks_state", "state", jstr),
                               ("webhooks_state_message", "state_message", jstr)])
    log.info("State message: %s", g.klippy.webhooks_state_message)


def parse_gcode_move(gcode_move):
    read_fields(g.klippy, gcode_move, [("gcode_move_speed_factor", "speed_factor", jfloat),
                                 ("gcode_move_speed", "speed", jfloat),
                                 ("gcode_move_extrude_factor", "extrude_factor", jfloat)])
    if jget(gcode_move, "homing_origin") is not None:
        for i in range(4):
            g.klippy.gcode_move_homing_origin[i] = jfloat(jpath(gcode_move, "homing_origin", i))
    if jget(gcode_move, "gcode_position") is not None:
        g.klippy.gcode_move_gcode_position[2] = jfloat(jpath(gcode_move, "gcode_position", 2))
        # round(float * 1000) / 1000 - float arithmetic (std::round(float) overload)
        g.klippy.gcode_z_position = f32(f32(c_round(f32(g.klippy.gcode_move_gcode_position[2] * 1000))) / 1000)


def parse_toolhead(toolhead):
    homed = jget(toolhead, "homed_axes")
    if isinstance(homed, str):
        g.klippy.homed_axes = homed.lower()
    if jget(toolhead, "position") is not None:
        position = g.klippy.toolhead_position
        for i in range(4):
            position[i] = jdouble(jpath(toolhead, "position", i))
        g.klippy.x_position = c_round(position[0] * 10) / 10
        g.klippy.y_position = c_round(position[1] * 10) / 10
        g.klippy.z_position = c_round(position[2] * 10) / 10

    for key, limits in (("axis_minimum", g.klippy.toolhead_axis_minimum),
                        ("axis_maximum", g.klippy.toolhead_axis_maximum)):
        if jget(toolhead, key) is not None:
            for i in range(4):
                limits[i] = jdouble(jpath(toolhead, key, i))


def parse_extruder(extruder):
    read_fields(g.klippy, extruder, [("extruder_temperature", "temperature", _temperature),
                               ("extruder_target", "target", _temperature)])


def parse_heater_bed(heater_bed):
    read_fields(g.klippy, heater_bed, [("heater_bed_temperature", "temperature", _temperature),
                                 ("heater_bed_target", "target", _temperature)])


def parse_heater_generic_hot(heater):
    read_fields(g.klippy, heater, [("hot_temperature", "temperature", _temperature),
                             ("hot_target", "target", _temperature)])


def parse_fan(fan):
    read_fields(g.klippy, fan, [("fan_speed", "speed", jfloat)])


def parse_heater_fan(heater_fan):
    read_fields(g.klippy, heater_fan, [("heater_fan_speed", "speed", jfloat)])


def parse_print_stats(print_stats):
    read_fields(g.klippy, print_stats, [("print_stats_state", "state", jstr),
                                  ("print_stats_filename", "filename", jstr),
                                  ("print_stats_print_duration", "print_duration", jfloat),
                                  ("print_stats_total_duration", "total_duration", jfloat)])


def parse_display_status(display_status):
    read_fields(g.klippy, display_status, [("display_status_progress", "progress", lambda v: c_int(jdouble(v) * 100))])


def parse_pause_resume(pause_resume):
    read_fields(g.klippy, pause_resume, [("pause_resume_is_paused", "is_paused", jbool)])


# object of the "status" of a subscription -> its parser
def parse_configfile(configfile):
    """The screws of the bed screws pages from [bed_screws] (screw1..3: x, y)"""
    screws = jpath(configfile, "settings", "bed_screws")
    if not isinstance(screws, dict):
        return
    for i in range(len(g.levelling.bed_screws)):
        xy = screws.get("screw%d" % (i + 1))
        if isinstance(xy, str):
            xy = xy.split(",")
        try:
            g.levelling.bed_screws[i] = (float(xy[0]), float(xy[1]))
        except (TypeError, ValueError, IndexError):
            log.warning("[bed_screws] screw%d: %s", i + 1, xy)


STATUS_PARSERS = {
    "idle_timeout": parse_idle_timeout,
    "bed_mesh": parse_bed_mesh,
    "webhooks": parse_webhooks,
    "gcode_move": parse_gcode_move,
    "toolhead": parse_toolhead,
    "extruder": parse_extruder,
    "heater_bed": parse_heater_bed,
    "heater_generic chamber": parse_heater_generic_hot,
    "fan": parse_fan,
    "heater_fan fan1": parse_heater_fan,
    "pause_resume": parse_pause_resume,
    "print_stats": parse_print_stats,
    "display_status": parse_display_status,
    "heater_fan my_nozzle_fan1": parse_printer_heater_fan_my_nozzle_fan1,
    "fan_generic cooling_fan": parse_printer_out_pin_fan0,
    "fan_generic auxiliary_cooling_fan": parse_printer_out_pin_fan2,
    "fan_generic chamber_circulation_fan": parse_printer_out_pin_fan3,
    "filament_switch_sensor fila": parse_filament_switch_sensor_fila,
    "output_pin caselight": parse_printer_caselight,
    "gcode_macro _SOUND": parse_printer_beep,
    "probe": parse_printer_probe,
    "configfile": parse_configfile,
}


def parse_subscribe_objects_status(status):
    """Parse the status of the subscribed objects"""
    for name, parser in STATUS_PARSERS.items():
        value = jget(status, name)
        if value is not None:
            parser(value)


def subscribe_objects_status():
    objects = {}
    objects["extruder"] = None
    objects["heater_generic chamber"] = None
    objects["heater_bed"] = None
    objects["gcode_move"] = None
    objects["fan"] = ["speed"]
    objects["heater_fan fan1"] = ["speed"]
    objects["toolhead"] = None
    objects["print_stats"] = ["print_duration", "total_duration", "filament_used", "filename", "state", "message"]
    objects["display_status"] = ["progress", "message"]
    objects["idle_timeout"] = ["state"]
    objects["pause_resume"] = ["is_paused"]
    objects["webhooks"] = ["state", "state_message"]
    objects["firmware_retraction"] = ["retract_length", "retract_speed", "unretract_extra_length",
                                      "unretract_speed"]
    objects["bed_mesh"] = None
    objects["heater_fan my_nozzle_fan1"] = None
    objects["filament_switch_sensor fila"] = ["filament_detected", "enabled"]
    objects["fan_generic cooling_fan"] = ["speed", "rpm"]
    objects["fan_generic auxiliary_cooling_fan"] = ["speed", "rpm"]
    objects["fan_generic chamber_circulation_fan"] = ["speed", "rpm"]
    objects["output_pin caselight"] = None
    objects["gcode_macro _SOUND"] = ["enabled"]
    objects["probe"] = None
    return objects


def get_cal_printing_time(print_time, estimated_time, progress):
    left_time = 0
    total_time = 0
    if progress <= 10:
        total_time = estimated_time
        left_time = total_time - print_time
    elif progress > 10:
        from librescreen.util.cpp import cdiv
        from librescreen.util.cpp import i32
        total_time = cdiv(i32(print_time * 100), progress)
        left_time = total_time - print_time
    return left_time


def parse_printer_info(result):
    if jget(result, "software_version") is not None:
        g.klippy.info_software_version = jstr(jget(result, "software_version"))
        log.info("Version: %s", g.klippy.info_software_version)
