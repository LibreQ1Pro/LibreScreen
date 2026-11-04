"""Dispatch of the messages received from Moonraker.

The responses are matched by the JSON-RPC id of the request (see
rpc_methods.method2id), notifications by their method name.
"""

import logging

from librescreen import state as g
from librescreen.moonraker.gcode_files import parse_file_estimated_time, parse_file_estimated_time_send
from librescreen.moonraker.gcode_responses import parse_gcode_response
from librescreen.moonraker.printer_status import (parse_printer_info,
                                            parse_server_history_totals,
                                            parse_subscribe_objects_status)
from librescreen.moonraker.rpc_requests import string2json
from librescreen.screen import pageids as ids
from librescreen.util.cpp import jeq, jget, jint, jpath, json_dump, jstr
from librescreen.util.guard import run_guarded

log = logging.getLogger(__name__)


# -- responses, matched by the id of the request ---------------------------------------------------------------------

def _file_metadata_response(response):
    parse_file_estimated_time(response)


def _object_status_response(response):
    if jeq(jget(response, "result"), "ok"):
        return
    status = jpath(response, "result", "status") if jget(response, "result") is not None else None
    if status is not None:
        log.debug("%s", json_dump(status))
        parse_subscribe_objects_status(status)


def _printer_info_response(response):
    if jget(response, "result") is not None:
        parse_printer_info(jget(response, "result"))


def _job_totals_response(response):      # total print time
    totals = jpath(response, "result", "job_totals") if jget(response, "result") is not None else None
    if totals is not None:
        parse_server_history_totals(totals)


RESPONSES = {
    3545: _file_metadata_response,
    4654: _object_status_response,
    5445: _printer_info_response,
    5656: _job_totals_response,
}


# -- notifications, by method ---------------------------------------------------------------------------------------

def _log(text):
    """A notification that is only logged."""
    return lambda message, response: log.debug(text)


def _gcode_response(message, response):
    log.info("%s", message)
    parse_gcode_response(jget(response, "params"))
    log.debug("Gcode response")


def _status_update(message, response):
    parse_subscribe_objects_status(jpath(response, "params", 0))


def _klippy_ready(message, response):
    from librescreen.printer import klipper
    log.debug("%s", json_dump(response))
    log.debug("Klippy is ready")
    # subscribe here
    klipper.get_object_status()
    klipper.sub_object_status()


def _klippy_disconnected(message, response):
    from librescreen.printer import klipper
    log.debug("Klippy disconnected")
    klipper.get_object_status()
    klipper.sub_object_status()


def _filelist_changed(message, response):
    g.files.filelist_changed = True
    log.debug("File list changed")
    g.screen.file_list_refreshed = False      # 4.4.22
    g.levelling.all_level_saving = True


def _history_changed(message, response):
    # 4.4.3 CLL web print information subscription
    if g.screen.page in (ids.PRINTING, ids.PRINT_ZOFFSET, ids.PRINT_FILAMENT, ids.PRINTING_2):
        return
    parse_file_estimated_time_send(jpath(response, "params", 0, "job", "metadata"))
    log.debug("History changed")


NOTIFICATIONS = {
    "notify_proc_stat_update": lambda message, response: None,
    "notify_gcode_response": _gcode_response,
    "notify_status_update": _status_update,
    "notify_klippy_ready": _klippy_ready,
    "notify_klippy_shutdown": _log("Klippy shutdown"),
    "notify_klippy_disconnected": _klippy_disconnected,
    "notify_filelist_changed": _filelist_changed,
    "notify_update_response": _log("Update manager response"),
    "notify_update_refreshed": _log("Update manager refreshed"),
    "notify_cpu_throttled": _log("Moonraker process statistics update"),
    "notify_history_changed": _history_changed,
    "notify_user_created": _log("Authorized user created"),
    "notify_user_deleted": _log("Authorized user deleted"),
    "notify_service_state_changed": lambda message, response: None,
    "notify_job_queue_changed": _log("Job queue changed"),
    "notify_button_event": _log("Button event"),
    "notify_announcement_update": _log("Announcement update event"),
    "notify_announcement_dismissed": _log("Announcement dismissed event"),
    "notify_announcement_wake": _log("Announcement wake event"),
    "notify_agent_event": _log("Agent event"),
    "notify_power_changed": _log("notify_power_changed"),
}


def handle_message(message):
    """Act on one message of Moonraker: a response to a request or a notification."""
    log.debug("Message of Moonraker: %.300s", message)
    try:
        response = string2json(message)
    except Exception as e:
        log.error("%s", str(e))
        return
    if not isinstance(response, dict):          # Moonraker sends objects; anything else is noise
        log.error("The message of Moonraker is not a JSON object: %.80s", message)
        return
    if jget(response, "id") is not None:
        log.debug("%s", json_dump(jget(response, "id")))
        handler = RESPONSES.get(jint(jget(response, "id")))
        if handler:
            log.debug("%s", json_dump(response))
            handler(response)

    if jget(response, "error") is not None:
        parse_error(jget(response, "error"))
    elif jget(response, "method") is not None:
        handler = NOTIFICATIONS.get(jstr(jget(response, "method")))
        if handler:
            handler(message, response)


def json_parse(arg=None):
    """Thread: handles the messages the websocket thread queues, in order (see state.message_queue)."""
    while True:
        run_guarded(handle_message, g.rpc.message_queue.get())


def parse_error(error):
    log.debug("%s", json_dump(error))
