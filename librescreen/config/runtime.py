"""Where things are: the settings of the deployment (Python only, not in the original).

The original has QIDI's image built in (``/root``, ``/home/mks``, ``ttyS1``, Moonraker on ``localhost:7125``).
The port reads an ini file instead; every key has a default, so no file is needed on a usual
Armbian / KIAUH installation::

    [moonraker]
    host = localhost
    port = 7125

    [screen]
    port = /dev/ttyS1
    baud = 115200
    transfer_baud = 921600      ; speed of the firmware download (--flash-screen)

    [paths]
    data_dir = ~/.local/share/librescreen     ; settings.ini (the saved settings of the screen)
    gcodes =                            ; empty: asked from Moonraker, then ~/printer_data/gcodes
    config =                            ; the same for the Klipper configuration (saved_variables.cfg)
    logs =                              ; and for the logs

    [log]
    level = info

The file is looked up in this order: ``--config FILE``, ``$LIBRESCREEN_CONFIG``, ``~/.config/librescreen/librescreen.ini``,
``/etc/librescreen/librescreen.ini``.  The first Moonraker host given on the command line wins over the file.
"""

import configparser
import os


DEFAULT_PATHS = ("~/.config/librescreen/librescreen.ini", "/etc/librescreen/librescreen.ini")


class Runtime(object):
    def __init__(self):
        self.moonraker_host = "localhost"
        self.moonraker_port = "7125"
        self.screen_port = "/dev/ttyS1"
        self.screen_baud = 115200
        self.transfer_baud = 921600
        self.data_dir = "~/.local/share/librescreen"
        self.gcodes = ""
        self.config = ""
        self.logs = ""
        self.log_level = "info"
        self.source = None          # the file the values were read from

    def moonraker_url(self, path=""):
        """``http://host:port/path``"""
        return "http://%s:%s/%s" % (self.moonraker_host, self.moonraker_port, path.lstrip("/"))

    def websocket_url(self):
        return "ws://%s:%s/websocket?" % (self.moonraker_host, self.moonraker_port)

    def data_path(self, name):
        """A file in the data directory (created when needed)."""
        directory = os.path.expanduser(self.data_dir)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, name)


cfg = Runtime()


def _candidates(path):
    if path:
        return [path]
    env = os.environ.get("LIBRESCREEN_CONFIG")
    return [env] if env else [os.path.expanduser(p) for p in DEFAULT_PATHS]


def load(path=None, host=None):
    """Read the settings (a missing file is no error unless it was named explicitly); ``host`` overrides the file."""
    global cfg
    cfg = Runtime()
    candidates = _candidates(path)
    parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    for candidate in candidates:
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                parser.read_file(f)
        except FileNotFoundError:
            if path or os.environ.get("LIBRESCREEN_CONFIG"):
                raise SystemExit("librescreen: the configuration file %s does not exist" % candidate)
            continue
        cfg.source = candidate
        break

    def get(section, key, default):
        return parser.get(section, key, fallback=str(default)).strip()

    try:
        cfg.moonraker_host = get("moonraker", "host", cfg.moonraker_host)
        cfg.moonraker_port = str(int(get("moonraker", "port", cfg.moonraker_port)))
        cfg.screen_port = get("screen", "port", cfg.screen_port)
        cfg.screen_baud = int(get("screen", "baud", cfg.screen_baud))
        cfg.transfer_baud = int(get("screen", "transfer_baud", cfg.transfer_baud))
    except ValueError as e:
        raise SystemExit("librescreen: %s: %s" % (cfg.source, e))
    cfg.data_dir = get("paths", "data_dir", cfg.data_dir)
    for key in ("gcodes", "config", "logs"):
        setattr(cfg, key, os.path.expanduser(get("paths", key, "")))
    cfg.log_level = get("log", "level", cfg.log_level)
    if host:
        cfg.moonraker_host = host
    return cfg
