"""Builders for the Moonraker JSON-RPC requests (https://moonraker.readthedocs.io)."""

from librescreen import state as g
from librescreen.moonraker.rpc_methods import method2command, method2id
from librescreen.util.cpp import json_dump, json_parse


# JSON message used by the makerbase client to identify the connection
STRING_IDENTIFY_CONNECTION = "{\"jsonrpc\":\"2.0\",\"method\":\"server.connection.identify\",\"params\":{\"client_name\":\"makerbase-client\",\"version\":\"0.0.1\",\"type\":\"web\",\"url\":\"http://makerbase.com/test\"},\"id\":4656}"
STRING_GET_KLIPPY_HOST_INFORMATION = "{\"jsonrpc\":\"2.0\",\"method\":\"printer.info\",\"id\":5445}"


def string2json(response):
    return json_parse(response)


def create_json_without_params(cmd):
    g.rpc.response_type_id = cmd
    api = {}
    api["jsonrpc"] = "2.0"
    api["method"] = method2command.get(cmd, "")
    api["id"] = method2id.get(cmd, 0)
    return json_dump(api)


def create_json(cmd, params):
    g.rpc.response_type_id = cmd
    api = {}
    api["jsonrpc"] = "2.0"
    api["method"] = method2command.get(cmd, "")
    api["params"] = params
    api["id"] = method2id.get(cmd, 0)
    return json_dump(api)


def json_emergency_stop():
    return create_json_without_params(0x04)


def json_query_printer_object_status(objects):
    params = {}
    params["objects"] = objects
    return create_json(0x12, params)


def json_subscribe_to_printer_object_status(objects):
    params = {}
    params["objects"] = objects
    return create_json(0x13, params)


# GCode APIs
def json_run_a_gcode(script):
    params = {}
    params["script"] = script
    return create_json(0x21, params)


# Print Management
def json_print_a_file(filename):
    params = {}
    params["filename"] = filename
    return create_json(0x31, params)


def json_get_gcode_metadata(filename):
    params = {}
    params["filename"] = filename
    return create_json(0x52, params)


def json_get_job_totals():
    return create_json_without_params(0xd2)
