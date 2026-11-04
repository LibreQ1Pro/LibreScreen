"""The pages of the automatic levelling, input shaping and bed calibration."""

import logging
import os
import time

from librescreen import state as g
from librescreen.pages.widgets import cut_after_point, face_group, heat_readout, heater_row
from librescreen.printer import klipper
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.util.cpp import f32, to_string

log = logging.getLogger(__name__)


def syntony_finish():
    log.debug("Printer ide_timeout state: %s", g.klippy.idle_timeout_state)
    log.debug("Printer webhooks state: %s", g.klippy.webhooks_state)
    if not g.levelling.syntony_finished:
        g.levelling.syntony_finished = True
        g.levelling.all_level_saving = False

    if g.klippy.idle_timeout_state == "Ready" and g.klippy.webhooks_state == "ready":
        log.debug("Printer webhooks state: %s", g.klippy.webhooks_state)
        time.sleep(10)
        os.sync()      # make sure the config file is saved

        g.levelling.all_level_saving = False
        klipper.sub_object_status()
        klipper.get_object_status()
        time.sleep(10)
        page_to(ids.LEVEL_MODE)
        log.info("Left from line 739")


def auto_level():
    for number, dist in enumerate((0.01, 0.05, 0.1, 0.5)):
        if g.levelling.auto_level_dist == f32(dist):
            face_group(["cstep_001", "cstep_005", "cstep_01", "cstep_05"], number)
            break


def syntony_move():
    if g.screen.temp_idle_state != g.klippy.idle_timeout_state:
        g.screen.temp_idle_state = g.klippy.idle_timeout_state
        log.debug("Printer ide_timeout state: %s", g.klippy.idle_timeout_state)
        log.debug("Printer webhooks state: %s", g.klippy.webhooks_state)

    if g.levelling.step_1:
        time.sleep(15)
        page_to(ids.SYNTONY_FINISH)
        g.levelling.step_1 = False


def auto_finish():
    if g.klippy.idle_timeout_state == "Idle" and g.klippy.webhooks_state == "ready":
        g.levelling.auto_level_finished = True


def auto_moving():
    heat_readout("bed", g.klippy.heater_bed_temperature, g.klippy.heater_bed_target)
    if g.levelling.step_1:
        g.port.face("steps_bar", "level_1")
        g.port.pco("step2_txt", "65535")
        g.port.pco("step1_txt", "42294")
        g.levelling.step_1 = False
    if g.levelling.step_2:
        g.port.face("steps_bar", "level_2")
        g.port.pco("step3_txt", "65535")
        g.port.pco("step2_txt", "42294")
        g.levelling.step_2 = False
    if g.levelling.step_3:
        g.port.face("steps_bar", "level_3")
        g.port.pco("step4_txt", "65535")
        g.port.pco("step3_txt", "42294")
        g.levelling.step_3 = False
        g.klippy.idle_timeout_state = "Printing"
    if g.levelling.step_4:
        time.sleep(15)
        page_to(ids.AUTO_FINISH)
        g.levelling.step_4 = False


def zoffset():
    i = 0
    while i < g.levelling.mesh_y_count:
        if i == 5:
            break
        j = 0
        while j < g.levelling.mesh_x_count:
            if j == 5:
                break
            temp = to_string(g.levelling.mesh_points[i][j])
            temp = cut_after_point(temp, 3)
            g.port.txt("cell_" + to_string(5 * i + j), temp)
            j += 1
        i += 1


def auto_heaterbed():
    heater_row("heat", g.klippy.heater_bed_temperature, g.klippy.heater_bed_target, icon="bed")


def bed_moving():
    if g.klippy.idle_timeout_state == "Ready":
        if g.screen.manual_count == 3:
            page_to(ids.PRE_BED_CALIBRATION)
        elif g.screen.manual_count == -2:
            page_to(ids.BED_FINISH)
        else:
            page_to(ids.BED_CALIBRATION)