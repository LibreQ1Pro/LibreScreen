"""The saved settings (settings.ini): reading and writing them, and loading the versions."""

import logging

from librescreen import state as g
from librescreen.config.inifile import open_settings, reset_settings, save_setting
from librescreen.moonraker import rest
from librescreen.moonraker.rpc_requests import json_get_job_totals
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to
from librescreen.util.cpp import to_string

log = logging.getLogger(__name__)


def get_extruder_target():
    ini = open_settings()
    g.config.extruder_target = ini.get_int("target", "extruder", 200)


def set_extruder_target(target):
    if target != 0:
        save_setting("target", "extruder", to_string(target))
    

def get_heater_bed_target():
    ini = open_settings()
    g.config.heater_bed_target = ini.get_int("target", "heaterbed", 40)


def set_heater_bed_target(target):
    if target != 0:
        log.debug("######## %s", target)
        save_setting("target", "heaterbed", to_string(target))
    

def get_hot_target():
    ini = open_settings()
    g.config.hot_target = ini.get_int("target", "hot", 40)


def set_hot_target(target):
    log.debug("######## %s", target)
    save_setting("target", "hot", to_string(target))


def get_total_time():
    g.ep.send(json_get_job_totals())


def get_oobe_enabled():
    ini = open_settings()
    g.config.oobe_enabled = ini.get_bool("oobe", "enable", 0)
    return g.config.oobe_enabled


def set_oobe_enabled(enable):
    save_setting("oobe", "enable", to_string(bool(enable)))


def restore_config():
    g.screen.main_picture_refreshed = False
    rest.request("POST", "server/history/reset_totals")
    rest.request("DELETE", "server/history/job?all=true")
    reset_settings()
    g.ep.run_gcode("SAVE_VARIABLE VARIABLE=z_offset VALUE=0")
    page_to(ids.MAIN)
