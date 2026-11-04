"""The pages of a print: progress, temperatures, z offset, pause / filament."""

import logging
import time

from librescreen import state as g
from librescreen.moonraker.printer_status import get_cal_printing_time
from librescreen.pages import file_list
from librescreen.pages.widgets import cut_after_point, face_group, fan_values, heater_row
from librescreen.printer import job
from librescreen.screen import pageids as ids
from librescreen.screen.text import POPUP_MSG_LINES, POPUP_MSG_WIDTH, wrap_text
from librescreen.screen.navigation import page_to
from librescreen.util.cpp import c_int, c_round, f32, to_string

log = logging.getLogger(__name__)


def stopping():
    log.debug("Printer ide_timeout state: %s", g.klippy.idle_timeout_state)
    log.debug("Printer webhooks state: %s", g.klippy.webhooks_state)
    if g.klippy.idle_timeout_state in ("Ready", "Idle"):         # Idle too: the page has no buttons, it must not wait for a state that came and went
        job.clear_previous_data()
        time.sleep(5)
        page_to(ids.MAIN)


def print_filament():
    g.port.txt("file_name", file_list.shown_name(file_list.file_name_only(g.klippy.print_stats_filename)))
    heater_row("nozzle", g.klippy.extruder_temperature, g.klippy.extruder_target)

    g.port.val("progress", to_string(g.klippy.display_status_progress))
    g.port.txt("progress_pct", to_string(g.klippy.display_status_progress))
    g.port.txt("time_elapsed", job.show_time(c_int(g.klippy.print_stats_print_duration)))
    g.port.txt("time_left", job.show_time(get_cal_printing_time(c_int(g.klippy.print_stats_print_duration),
                                                                 g.files.meta_estimated_time,
                                                                 g.klippy.display_status_progress)))

    if g.klippy.print_stats_state == "paused":
        g.klippy.ready = True

    # 4.4.2 CLL support mates and hall filament width sensors
    if not g.klippy.filament_detected:
        time.sleep(1)
        g.klippy.ready = False
        job.set_print_pause()
        page_to(ids.PRINT_NO_FILAMENT)

    if g.klippy.print_stats_state == "printing":
        if g.klippy.ready:
            g.klippy.ready = False
            page_to(ids.PRINTING)

    if g.klippy.print_stats_state == "standby":
        page_to(ids.PRINT_STOPPING)

    if g.klippy.print_stats_state == "error":
        page_to(ids.GCODE_ERROR)
        job.cancel_print()
        job.clear_previous_data()
        g.port.txt("msg", wrap_text("G-code error: " + g.screen.error_message, POPUP_MSG_WIDTH, POPUP_MSG_LINES))

    # 4.4.2 CLL a long pause that stops the print switches the page
    if g.klippy.idle_timeout_state == "Idle":
        g.ep.run_gcode("G28\n")
        job.cancel_print()


def offset(intern_zoffset):
    g.klippy.intern_z_offset = f32(intern_zoffset)
    g.klippy.z_offset = f32(g.klippy.intern_z_offset + g.klippy.extern_z_offset)


def zoffset_buttons():
    sel = {0.01: 0, 0.05: 1, 0.1: 2, 0.5: 3}
    for dist, number in sel.items():
        if g.klippy.set_offset == f32(dist):
            face_group(("step_001", "step_005", "step_01", "step_05"), number, "z_on", "z_off")
            return


def printing_zoffset():
    z_offset = to_string(g.klippy.gcode_move_homing_origin[2])
    show_gcode_z = to_string(g.klippy.gcode_z_position)
    z_offset = cut_after_point(z_offset, 4)
    show_gcode_z = cut_after_point(show_gcode_z, 4)
    g.port.txt("file_name", file_list.shown_name(file_list.file_name_only(g.klippy.print_stats_filename)))
    g.port.txt("gcode_z", show_gcode_z)
    g.port.txt("z_offset", z_offset)
    g.port.txt("time_elapsed", job.show_time(c_int(g.klippy.print_stats_print_duration)))
    g.port.txt("progress_pct", to_string(g.klippy.display_status_progress))
    g.port.txt("time_left", job.show_time(get_cal_printing_time(c_int(g.klippy.print_stats_print_duration),
                                                                 g.files.meta_estimated_time,
                                                                 g.klippy.display_status_progress)))
    g.port.val("progress", to_string(g.klippy.display_status_progress))

    zoffset_buttons()

    if g.klippy.print_stats_state == "printing":
        g.klippy.ready = True

    if g.klippy.fila_sensor_enabled:
        if not g.klippy.fila_sensor_detected:
            g.klippy.ready = False
            job.set_print_pause()
            page_to(ids.PRINT_NO_FILAMENT_2)

    # 4.4.2 CLL support mates and hall filament width sensors
    if not g.klippy.filament_detected:
        time.sleep(1)
        g.klippy.ready = False
        job.set_print_pause()
        page_to(ids.PRINT_NO_FILAMENT)

    if g.klippy.print_stats_state == "standby":
        page_to(ids.PRINT_STOPPING)

    if g.klippy.print_stats_state == "paused":
        if g.klippy.ready:
            g.klippy.ready = False
            page_to(ids.PRINT_FILAMENT)

    if g.klippy.print_stats_state == "complete":
        time_duration = job.show_time(c_int(g.klippy.print_stats_print_duration))
        job.clear_previous_data()
        time.sleep(5)
        page_to(ids.PRINT_FINISH)
        g.port.txt("time_txt", time_duration)

    if g.klippy.print_stats_state == "error":
        page_to(ids.GCODE_ERROR)
        job.cancel_print()
        job.clear_previous_data()
        g.port.txt("msg", wrap_text("G-code error: " + g.screen.error_message, POPUP_MSG_WIDTH, POPUP_MSG_LINES))


def printing_keyboard_mute_button():
    # 4.4.22 silent mode button of the keyboard
    g.port.face("mute_btn", "off" if not g.screen.muted else "on")


def printing_first_page():
    fan_values()
    heater_row("nozzle", g.klippy.extruder_temperature, g.klippy.extruder_target)
    heater_row("bed", g.klippy.heater_bed_temperature, g.klippy.heater_bed_target)
    heater_row("chamber", g.klippy.hot_temperature, g.klippy.hot_target)     # CLL chamber temperature

    shown = "1" if g.screen.show_preview_gimage_completed else "0"
    g.port.vis("thumb", shown)
    g.port.val("thumb_flag", shown)


def printing_second_page():
    # written on every refresh: the sender (tx) skips what the screen has already, and sends it again when the page is shown anew (also by the
    # keyboard, which brings the page back with its initial "---")
    for widget, factor in (("speed_val", g.klippy.gcode_move_speed_factor), ("flow_val", g.klippy.gcode_move_extrude_factor)):     # CLL speed / extrusion factor
        g.port.txt(widget, to_string(c_int(c_round(f32(factor * 100)))))

    g.port.face("light2_btn", "off" if g.klippy.caselight_value == 0 else "on")      # 4.4.22 LED state
    fan_values()


def printing_state_changes():
    """Filament runout and the end of the print, as Klipper reports them."""
    if g.klippy.print_stats_state == "printing":
        g.klippy.ready = True

    if g.klippy.fila_sensor_enabled:
        if not g.klippy.fila_sensor_detected:
            g.klippy.ready = False
            job.set_print_pause()
            page_to(ids.PRINT_NO_FILAMENT_2)

    if not g.klippy.filament_detected:
        time.sleep(1)
        g.klippy.ready = False
        job.set_print_pause()
        page_to(ids.PRINT_NO_FILAMENT)

    state = g.klippy.print_stats_state
    if state == "complete":
        time_duration = job.show_time(c_int(g.klippy.print_stats_print_duration))
        job.clear_previous_data()
        time.sleep(5)
        page_to(ids.PRINT_FINISH)
        g.port.txt("time_txt", time_duration)
    elif state == "paused":
        if g.klippy.ready:
            g.klippy.ready = False
            page_to(ids.PRINT_FILAMENT)
    elif state == "standby":
        page_to(ids.PRINT_STOPPING)
    elif state == "error":
        page_to(ids.GCODE_ERROR)
        job.cancel_print()
        job.clear_previous_data()
        g.port.txt("msg", wrap_text("G-code error: " + g.screen.error_message, POPUP_MSG_WIDTH, POPUP_MSG_LINES))


def printing():
    z_offset = to_string(g.klippy.gcode_move_homing_origin[2])
    z_offset = cut_after_point(z_offset, 4)

    g.port.val("progress", to_string(g.klippy.display_status_progress))
    g.port.txt("progress_pct", to_string(g.klippy.display_status_progress))
    g.port.txt("time_elapsed", job.show_time(c_int(g.klippy.print_stats_print_duration)))
    g.port.txt("time_left", job.show_time(get_cal_printing_time(c_int(g.klippy.print_stats_print_duration),
                                                                 g.files.meta_estimated_time,
                                                                 g.klippy.display_status_progress)))
    g.port.txt("file_name", file_list.shown_name(file_list.file_name_only(g.klippy.print_stats_filename)))

    # While the keyboard (keybdB) is shown the page behind it is not on the screen: its objects (zoffset_val, ...)
    # do not exist there and every instruction for them is answered with "invalid variable name".
    # The keyboard page returns to the printing page after the value (or "back") frame, which ends the flag,
    # and the page is refreshed again - the z offset first, the page starts with the designer's "-1.000".
    if g.screen.printing_keyboard_enabled:
        printing_keyboard_mute_button()
    elif g.screen.page == ids.PRINTING:         # CLL refresh only while the keyboard is not shown
        printing_first_page()
    elif g.screen.page == ids.PRINTING_2:
        g.port.txt("zoffset_val", z_offset)
        printing_second_page()

    printing_state_changes()


def clear_printing_arg():
    g.shown.extruder_temperature = 0
    g.shown.extruder_target = 0
    g.shown.heater_bed_target = 0
    g.shown.heater_bed_temperature = 0
    g.shown.hot_target = 0
    g.shown.hot_temperature = 0
    g.shown.out_pin_fan0_value = 0.0
    g.shown.out_pin_fan2_value = 0.0
    g.shown.out_pin_fan3_value = 0.0
