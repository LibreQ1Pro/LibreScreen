"""The configuration of the deployment (librescreen/config/runtime.py)."""

import os
import tempfile
import unittest
from unittest import mock

from librescreen.config import runtime


class RuntimeConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        env = {k: v for k, v in os.environ.items() if k != "LIBRESCREEN_CONFIG"}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: setattr(runtime, "cfg", runtime.Runtime()))     # the other tests get the defaults

    def write(self, text):
        path = os.path.join(self.dir.name, "librescreen.ini")
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_defaults_without_a_file(self):
        with mock.patch.object(runtime, "DEFAULT_PATHS", (os.path.join(self.dir.name, "missing.ini"),)):
            cfg = runtime.load()
        self.assertEqual((cfg.moonraker_host, cfg.moonraker_port, cfg.screen_port), ("localhost", "7125", "/dev/ttyS1"))
        self.assertEqual((cfg.screen_baud, cfg.transfer_baud), (115200, 921600))
        self.assertEqual(cfg.moonraker_url("/server/info"), "http://localhost:7125/server/info")
        self.assertEqual(cfg.websocket_url(), "ws://localhost:7125/websocket?")
        self.assertEqual((cfg.gcodes, cfg.config, cfg.logs), ("", "", ""))

    def test_values_of_the_file(self):
        path = self.write("[moonraker]\nhost = printer.lan\nport = 7126 ; comment\n[screen]\nport = /dev/ttyUSB0\n"
                          "[paths]\ngcodes = ~/gc\ndata_dir = %s/data\n" % self.dir.name)
        cfg = runtime.load(path)
        self.assertEqual((cfg.moonraker_host, cfg.moonraker_port, cfg.screen_port), ("printer.lan", "7126", "/dev/ttyUSB0"))
        self.assertEqual(cfg.gcodes, os.path.expanduser("~/gc"))
        self.assertTrue(cfg.data_path("settings.ini").startswith(self.dir.name + "/data/"))
        self.assertTrue(os.path.isdir(self.dir.name + "/data"))

    def test_the_host_of_the_command_line_wins(self):
        path = self.write("[moonraker]\nhost = printer.lan\n")
        self.assertEqual(runtime.load(path, "other").moonraker_host, "other")

    def test_a_named_file_must_exist(self):
        with self.assertRaises(SystemExit):
            runtime.load(os.path.join(self.dir.name, "missing.ini"))

    def test_a_bad_number_is_reported(self):
        path = self.write("[moonraker]\nport = http\n")
        with self.assertRaises(SystemExit):
            runtime.load(path)

    def test_the_environment_names_the_file(self):
        path = self.write("[screen]\nbaud = 9600\n")
        with mock.patch.dict(os.environ, {"LIBRESCREEN_CONFIG": path}):
            self.assertEqual(runtime.load().screen_baud, 9600)


if __name__ == "__main__":
    unittest.main()
