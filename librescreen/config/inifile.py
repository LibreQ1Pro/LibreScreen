"""Access to settings.ini (the settings of the screen backend)."""

import logging
import os
import re

from librescreen.config import runtime
from librescreen.util.cpp import i32, strtol

log = logging.getLogger(__name__)

def _inipath():
    """settings.ini in the data directory of the configuration (see runtime.py)"""
    return runtime.cfg.data_path("settings.ini")


# Python only: written when the file does not exist (QIDI's system image comes
# with one, other systems do not, and the settings could not be saved).  The
# values are the defaults the program uses when a key is missing.
DEFAULT_SETTINGS = """[target]
extruder = 200
heaterbed = 40
hot = 40

[oobe]
enable = 0
"""


def _create_default_settings(path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError:
        return          # exists already (or the directory is missing)
    with os.fdopen(fd, "w") as ini:
        ini.write(DEFAULT_SETTINGS)
    log.debug("%s", "Created " + path + " with the default settings")


class IniFile:
    """An ini file: ``[section]`` lines and ``key = value`` lines, keys and sections in lower case.

    ``values`` is None when the file does not exist or has a syntax error; the getters then give the default.
    """

    def __init__(self, path):
        self.path = path
        self.values = self._parse(path)
        if self.values is None:
            log.debug("Ini parse failure!")

    @staticmethod
    def _parse(path):
        try:
            with open(path, "rb") as f:
                text = f.read().decode("utf-8", "replace")
        except OSError:
            return None
        values = {}
        section = ""
        pending = ""
        for number, raw in enumerate(text.split("\n"), 1):
            line = pending + raw.rstrip()
            if line.endswith("\\"):          # the line continues
                pending = line[:-1]
                continue
            pending = ""
            line = line.strip()
            if not line or line[0] in "#;":
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().lower()
                values.setdefault(section, {})
                continue
            m = _KEY_VALUE.match(line)
            if not m:
                log.error("iniparser: syntax error in %s (%d):\n-> %s", path, number, line)
                return None
            key, quoted, plain = m.group(1).strip().lower(), m.group(2) or m.group(3), m.group(4)
            if quoted is None:
                quoted = (plain or "").split(";")[0].split("#")[0].strip()
            values.setdefault(section, {})[key] = quoted
        return values

    def _find(self, section, key):
        if self.values is None:
            return None
        return self.values.get(section.lower(), {}).get(key.lower())

    def get_string(self, section, key, default):
        value = self._find(section, key)
        return default if value is None else value

    def get_int(self, section, key, default):
        value = self._find(section, key)
        return default if value is None else i32(strtol(value, 0))

    def get_bool(self, section, key, default):
        first = (self._find(section, key) or "")[:1]
        if first in ("y", "Y", "1", "t", "T"):
            return True
        if first in ("n", "N", "0", "f", "F"):
            return False
        return bool(default)

    def set(self, section, key, value):
        if self.values is not None:
            self.values.setdefault(section.lower(), {})[key.lower()] = value

    def save(self):
        """Write the file back, in the layout the original program wrote."""
        if self.values is None:
            return
        try:
            ini = open(self.path, "wb")
        except OSError:
            print("[error] open settings.ini failed", end="")
            return
        with ini:
            for section, entries in self.values.items():
                if not section:
                    continue
                ini.write(("\n[%s]\n" % section).encode())
                for key, value in entries.items():
                    ini.write(("%-30s = %s\n" % (key, value)).encode())
                ini.write(b"\n")
            ini.write(b"\n")
            ini.flush()
            os.fsync(ini.fileno())          # the original runs sync(1) after it


# key = "value" | key = 'value' | key = value ; comment | key = (empty)
_KEY_VALUE = re.compile(r"([^=]+?)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\"']*?))\s*$")


def reset_settings():
    """Back to the defaults (what a new installation starts with)."""
    with open(_inipath(), "w") as ini:
        ini.write(DEFAULT_SETTINGS)
        ini.flush()
        os.fsync(ini.fileno())


def open_settings():
    """settings.ini, created with the defaults when it does not exist."""
    if not os.path.exists(_inipath()):
        _create_default_settings(_inipath())
    return IniFile(_inipath())


def save_setting(section, key, value):
    """Change one value of settings.ini and write the file."""
    ini = open_settings()
    ini.set(section, key, value)
    ini.save()
