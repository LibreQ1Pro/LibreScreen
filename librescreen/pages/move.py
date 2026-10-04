"""The move page and its pop-ups."""

from librescreen import state as g
from librescreen.pages.widgets import cut_after_point, segmented
from librescreen.printer import job
from librescreen.screen import pageids as ids
from librescreen.util.cpp import f32, to_string


UNKNOWN_POSITION = "---.-"


def move_page():
    for axis, value in (("x", g.klippy.x_position), ("y", g.klippy.y_position), ("z", g.klippy.z_position)):
        # an axis that is not homed has no position yet
        g.port.txt(axis + "_pos", cut_after_point(to_string(value), 2) if axis in g.klippy.homed_axes else UNKNOWN_POSITION)

    # CLL highlight the selected distance
    for dist, look in ((0.1, "d01"), (1.0, "d1"), (10, "d10")):
        if g.klippy.move_dist == f32(dist):
            segmented("dist_seg", (("d01", "dist_01_lbl"), ("d1", "dist_1_lbl"), ("d10", "dist_10_lbl")), look)


def move_home_tips():
    g.screen.jump_move_pop_2 = True


def move_tips():
    g.screen.jump_move_pop_1 = True
    if g.screen.page in (ids.PRINTING, ids.PRINT_ZOFFSET, ids.PRINT_FILAMENT,
                             ids.PRINTING_2):
        job.cancel_print()
