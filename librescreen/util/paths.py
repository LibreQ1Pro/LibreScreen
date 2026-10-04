"""Directories of the printer's files (Python only, not in the original).

The original has QIDI's layout built in: ``/home/mks/gcode_files`` (the gcode
files, with USB drives mounted at ``sda1``), ``/home/mks/klipper_config`` and
``/home/mks/klipper_logs``.  Newer Moonraker installations (KIAUH, Armbian)
use ``~/printer_data/gcodes``, ``~/printer_data/config`` and
``~/printer_data/logs`` instead.

A directory named in the configuration file (``[paths]``, see
``librescreen/config/runtime.py``) is used as it is.  Otherwise the port asks
Moonraker for its roots (``/server/files/roots``) and keeps the answer once
Moonraker has answered; until then (Moonraker not started yet)
``~/printer_data`` is used.
"""

import json
import os
import threading
import time
import urllib.request

from librescreen.config import runtime


RETRY_SECONDS = 5.0

_roots = None
_last_try = 0.0
_lock = threading.Lock()


def _moonraker_roots():
    """{root name: path} from Moonraker; {} if it answered without them,
    None if it could not be reached."""
    try:
        with urllib.request.urlopen(runtime.cfg.moonraker_url("server/files/roots"), timeout=2) as resp:
            result = json.loads(resp.read().decode("utf-8")).get("result", [])
        return {r["name"]: r["path"].rstrip("/") for r in result if r.get("name") and r.get("path")}
    except urllib.error.HTTPError:
        return {}           # an older Moonraker (or none) answering the port
    except Exception:
        return None


def _get(name):
    global _roots, _last_try
    named = getattr(runtime.cfg, name)
    if named:
        return named.rstrip("/")
    with _lock:
        if _roots is None and time.time() - _last_try >= RETRY_SECONDS:
            _last_try = time.time()
            _roots = _moonraker_roots()
        roots = _roots
    if roots and roots.get(name):
        return roots[name]
    return os.path.join(os.path.expanduser("~/printer_data"), name)


def gcode_files():
    """the gcode directory (``/home/mks/gcode_files`` of the original)"""
    return _get("gcodes")


def klipper_config():
    """the Klipper configuration directory (``/home/mks/klipper_config`` of the original)"""
    return _get("config")


def klipper_logs():
    """the log directory (``/home/mks/klipper_logs`` of the original)"""
    return _get("logs")
