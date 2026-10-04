"""Subscriptions, restarts and plain gcode: talking to Klipper itself."""

from librescreen import state as g
from librescreen.moonraker.printer_status import subscribe_objects_status
from librescreen.moonraker.rpc_requests import json_query_printer_object_status, json_subscribe_to_printer_object_status
from librescreen.screen import pageids as ids
from librescreen.screen.navigation import page_to


def sub_object_status():
    g.ep.send(json_subscribe_to_printer_object_status(subscribe_objects_status()))


def get_object_status():
    objects = subscribe_objects_status()
    # Not subscribed: the settings of the config only change with a restart of Klipper
    objects["configfile"] = ["settings"]
    g.ep.send(json_query_printer_object_status(objects))


def reset_klipper():
    g.ep.run_gcode("RESTART\n")


def reset_firmware():
    g.ep.run_gcode("FIRMWARE_RESTART\n")


def go_to_reset():
    if g.klippy.webhooks_state == "shutdown":
        page_to(ids.RESET)
    else:
        page_to(ids.SYS_OK)


def send_gcode(command):
    g.ep.run_gcode(command)
