"""Clicks on the move page and the filament pages. Each function gets the page id and the widget id the screen sent; HANDLERS maps pages to them."""

from librescreen import state as g
from librescreen.pages import file_list, navigation
from librescreen.printer import heating, job, klipper, motion
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to


def move(page_id, widget_id):
    if widget_id == ids.MOVE_SET_01:
        motion.set_move_dist(0.1)
    elif widget_id == ids.MOVE_SET_1:
        motion.set_move_dist(1.0)
    elif widget_id == ids.MOVE_SET_10:
        motion.set_move_dist(10.0)
    elif widget_id == ids.MOVE_Z_UP:
        motion.move_z_decrease()
    elif widget_id == ids.MOVE_Z_DOWN:
        motion.move_z_increase()
    elif widget_id == ids.MOVE_MOTOR:
        motion.move_motors_off()
    elif widget_id == ids.MOVE_X_UP:
        motion.move_x_increase()
    elif widget_id == ids.MOVE_X_DOWN:
        motion.move_x_decrease()
    elif widget_id == ids.MOVE_Y_UP:
        motion.move_y_increase()
    elif widget_id == ids.MOVE_Y_DOWN:
        motion.move_y_decrease()
    elif widget_id == ids.MOVE_HOME:
        motion.move_home()
    elif widget_id == ids.MOVE_TO_FILAMENT:
        page_to(ids.FILAMENT)
        g.screen.adjust_mode = "Filament"
    elif widget_id == ids.ALL_TO_MAIN:
        page_to(ids.MAIN)
    elif widget_id == ids.ALL_TO_FILE_LIST:
        file_list.go_to_file_list()
    elif widget_id == ids.ALL_TO_ADJUST:
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        navigation.go_to_setting()


def move_pop_1(page_id, widget_id):
    if widget_id == ids.MOVE_POP_1_YES:
        if (g.screen.previous_page == ids.PRINTING or g.screen.previous_page == ids.PRINT_ZOFFSET
                or g.screen.previous_page == ids.PRINTING_2):
            job.cancel_print()
            page_to(ids.PRINT_STOPPING)
        else:
            page_to(ids.MOVE)


def move_pop_2(page_id, widget_id):
    if widget_id == ids.MOVE_POP_2_YES:
        page_to(ids.MOVE)
        motion.move_home()
    elif widget_id == ids.MOVE_POP_2_NO:
        page_to(ids.MOVE)


def filament_kb(page_id, widget_id):
    from_main = g.screen.temperature_from_main
    g.screen.temperature_from_main = False
    if widget_id == ids.FILAMENT_KB_BACK and from_main:
        page_to(ids.MAIN)
    elif widget_id == ids.ALL_TO_MAIN:
        page_to(ids.MAIN)
    elif widget_id == ids.ALL_TO_FILE_LIST:
        file_list.go_to_file_list()
    elif widget_id == ids.ALL_TO_ADJUST:
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        navigation.go_to_setting()
    elif widget_id == ids.FILAMENT_KB_BACK:
        page_to(ids.FILAMENT)


def filament(page_id, widget_id):
    if widget_id == ids.ALL_TO_MAIN:
        page_to(ids.MAIN)
    elif widget_id == ids.ALL_TO_FILE_LIST:
        file_list.go_to_file_list()
    elif widget_id == ids.ALL_TO_ADJUST:
        pass
    elif widget_id == ids.ALL_TO_SETTING:
        navigation.go_to_setting()
    elif widget_id in (ids.FILAMENT_SET_EXTRUDER, ids.FILAMENT_SET_HEATERBED, ids.FILAMENT_SET_HOT,
                       ids.FILAMENT_OPEN_FAN_1, ids.FILAMENT_OPEN_FAN_2, ids.FILAMENT_OPEN_FAN_3):
        page_to(ids.FILAMENT_KB)
    elif widget_id == ids.FILAMENT_EXTRUDER_UP:
        g.klippy.idle_timeout_state = "Printing"
        g.screen.filament_extrude_button = True
        motion.start_retract()
    elif widget_id == ids.FILAMENT_EXTRUDER_DOWN:
        g.klippy.idle_timeout_state = "Printing"
        g.screen.filament_extrude_button = True
        motion.start_extrude()
    elif widget_id == ids.FILAMENT_EXTRUDER_ON_OFF:
        heating.filament_extruder_target()
    elif widget_id == ids.FILAMENT_HEATERBED_ON_OFF:
        heating.filament_heater_bed_target()
    elif widget_id == ids.FILAMENT_HOT_ON_OFF:
        heating.filament_hot_target()
    elif widget_id == ids.FILAMENT_LOAD:
        g.screen.load_mode = True
        page_to(ids.PRE_HEAT)
    elif widget_id == ids.FILAMENT_UNLOAD:
        g.screen.load_mode = False
        page_to(ids.PRE_HEAT)
    elif widget_id == ids.FILAMENT_SET_10:
        motion.set_print_filament_dist(10)
    elif widget_id == ids.FILAMENT_SET_50:
        motion.set_print_filament_dist(50)
    elif widget_id == ids.FILAMENT_SET_100:
        motion.set_print_filament_dist(100)
    elif widget_id == ids.FILAMENT_TO_MOVE:
        page_to(ids.MOVE)
        g.screen.adjust_mode = "Move"


def filament_pop_1(page_id, widget_id):
    if widget_id == ids.FILAMENT_POP_1_YES:
        g.klippy.idle_timeout_state = "Ready"
        page_to(ids.FILAMENT)


def filament_pop_2(page_id, widget_id):
    if widget_id == ids.FILAMENT_POP_2_YES:
        klipper.send_gcode("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0\n")
        if g.klippy.print_stats_state == "paused":
            page_to(ids.PRINT_FILAMENT)
        else:
            page_to(ids.FILAMENT)
    elif widget_id == ids.FILAMENT_POP_2_TO_LOAD:
        g.screen.load_mode = True
        page_to(ids.PRE_HEAT)
    elif widget_id == ids.FILAMENT_POP_2_NEXT:
        motion.filament_load()
    elif widget_id == ids.FILAMENT_POP_2_BACK:
        page_to(ids.UNLOAD_MODE)


def filament_pop_3(page_id, widget_id):
    if widget_id == ids.FILAMENT_POP_3_NEXT:
        motion.filament_load()
    elif widget_id == ids.FILAMENT_POP_3_YES:
        klipper.send_gcode("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0\n")
        if g.klippy.print_stats_state == "paused":
            page_to(ids.PRINT_FILAMENT)
        else:
            page_to(ids.FILAMENT)
    elif widget_id == ids.FILAMENT_POP_3_RETRY:
        g.screen.load_mode = True
        page_to(ids.FILAMENT_POP_3)
        motion.filament_load()
    elif widget_id == ids.FILAMENT_POP_3_BACK:
        page_to(ids.PRE_HEAT)


def filament_unload_finish(page_id, widget_id):
    if widget_id == ids.FILAMENT_UNLOAD_FINISH_YES:
        page_to(ids.FILAMENT)


def pre_heat(page_id, widget_id):
    if widget_id in (ids.PRE_HEAT_SET_220, ids.PRE_HEAT_SET_250, ids.PRE_HEAT_SET_300):
        g.screen.load_target = {ids.PRE_HEAT_SET_220: 220, ids.PRE_HEAT_SET_250: 250,
                         ids.PRE_HEAT_SET_300: 300}[widget_id]
        if g.screen.load_mode:
            page_to(ids.FILAMENT_POP_3)
        else:
            page_to(ids.UNLOAD_MODE)
    elif widget_id == ids.PRE_HEAT_BACK:
        if g.klippy.print_stats_state == "paused":
            page_to(ids.PRINT_FILAMENT)
        else:
            page_to(ids.FILAMENT)


def unload_mode(page_id, widget_id):
    if widget_id == ids.UNLOAD_MODE_MANUAL:
        page_to(ids.FILAMENT_POP_2)
    elif widget_id == ids.UNLOAD_MODE_AUTO:
        page_to(ids.AUTO_UNLOAD)
        motion.filament_unload()
    elif widget_id == ids.UNLOAD_MODE_BACK:
        page_to(ids.PRE_HEAT)


def auto_unload(page_id, widget_id):
    if widget_id == ids.AUTO_UNLOAD_YES:
        klipper.send_gcode("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0\n")
        if g.klippy.print_stats_state == "paused":
            page_to(ids.PRINT_FILAMENT)
        else:
            page_to(ids.FILAMENT)
    elif widget_id == ids.AUTO_UNLOAD_TO_LOAD:
        g.screen.load_mode = True
        page_to(ids.PRE_HEAT)


HANDLERS = {
    ids.MOVE: move,
    ids.MOVE_POP_1: move_pop_1,
    ids.MOVE_POP_2: move_pop_2,
    ids.FILAMENT_KB: filament_kb,
    ids.FILAMENT: filament,
    ids.FILAMENT_POP_1: filament_pop_1,
    ids.FILAMENT_POP_2: filament_pop_2,
    ids.FILAMENT_POP_3: filament_pop_3,
    ids.FILAMENT_UNLOAD_FINISH: filament_unload_finish,
    ids.PRE_HEAT: pre_heat,
    ids.UNLOAD_MODE: unload_mode,
    ids.AUTO_UNLOAD: auto_unload,
}
