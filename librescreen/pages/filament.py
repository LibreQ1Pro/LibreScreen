"""The filament page, its pop-ups and the unload page."""

from librescreen import state as g
from librescreen.pages.widgets import fan_values, heat_readout, heater_row, segmented
from librescreen.screen import pageids as ids


def filament_tips():
    if g.screen.page == ids.OPEN_FILAMENTVIDEO_3:
        pass
    elif g.screen.page == ids.PRINT_FILAMENT:
        g.screen.jump_print_low_temp = True
    else:
        g.screen.jump_filament_pop_1 = True


def filament_pop():
    heat_readout("nozzle", g.klippy.extruder_temperature, g.klippy.extruder_target)
    if g.levelling.step_1:
        g.levelling.step_1 = False
        g.port.face("steps_bar", "load_2")
        g.port.pco("step2_txt", "65535")
        g.port.pco("step1_txt", "42294")
        g.port.pco("nozzle_temp", "42294")
    if g.levelling.step_2 and g.klippy.idle_timeout_state == "Ready":
        g.levelling.step_2 = False
        g.port.face("steps_bar", "load_3")
        g.port.pco("step3_txt", "65535")
        g.port.pco("step2_txt", "42294")
        for name in ("done_btn", "alt_btn"):
            g.port.vis(name, "1")


def filament():
    for heater, current, target in (("nozzle", g.klippy.extruder_temperature, g.klippy.extruder_target),
                                    ("bed", g.klippy.heater_bed_temperature, g.klippy.heater_bed_target),
                                    ("chamber", g.klippy.hot_temperature, g.klippy.hot_target)):
        heater_row(heater, current, target)
    fan_values()
    look = {10: "s10", 50: "s50", 100: "s100"}.get(g.klippy.filament_extruder_dist)
    if look is not None:
        segmented("step_seg", (("s10", "step_10_lbl"), ("s50", "step_50_lbl"), ("s100", "step_100_lbl")), look)


def auto_unload():
    heat_readout("nozzle", g.klippy.extruder_temperature, g.klippy.extruder_target)
    if g.levelling.step_1:
        g.levelling.step_1 = False
        g.port.face("steps_bar", "unload_1")
        g.port.pco("step2_txt", "65535")
        g.port.pco("step1_txt", "42294")
    if g.levelling.step_2:
        g.levelling.step_2 = False
        g.port.face("steps_bar", "unload_2")
        g.port.pco("step3_txt", "65535")
        g.port.pco("step2_txt", "42294")
        for name in ("load_btn", "ok"):
            g.port.vis(name, "1")
