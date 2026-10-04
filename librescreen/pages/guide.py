"""The pages of the first-start guide that show printer state."""

from librescreen import state as g
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.pages.widgets import heater_row
from librescreen.util.cpp import to_string


def open_filament_video_2():
    """"Load filament: heat": the readout, and the next button that waits until the nozzle has reached the target."""
    current, target = g.klippy.extruder_temperature, g.klippy.extruder_target
    heater_row("heat", current, target, icon="nozzle")
    g.port.val("cur_val", to_string(round(current)))        # the screen checks the same condition when the button is tapped
    g.port.val("tar_val", to_string(round(target)))
    hot = target > 0 and current + 10 >= target and current + 10 >= 185
    g.port.face("next", "ready" if hot else "wait")
    g.port.tsw("next", "1" if hot else "0")


def open_moving():
    """4.4.22: leave the "moving" page of the guide once Klipper is idle again."""
    if g.klippy.idle_timeout_state != "Printing":
        page_to(ids.OPEN_FILAMENTVIDEO_0)
