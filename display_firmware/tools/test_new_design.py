#!/usr/bin/env python3
"""The first migrated display/backend slice, tested together in Docker with hmi-builder mounted.

    HMI_BUILDER=/opt/hmi-builder python3 display_firmware/tools/test_new_design.py

Tests the real component names/attributes, touches, version warning, idle placeholders and .zi widths.
No printer services, network or physical serial devices are used.
"""
import unittest
from unittest.mock import patch

from gen_project import ROOT, load
import tile_core as core

core.builder_path()
from hmi_emu.device import Device, END
from hmi_emu.project import Project
from hmi_emu.render import Renderer
import hmi_font

from librescreen import state as g
from librescreen.pages import home, file_list
from librescreen.screen import pageids as ids
from librescreen.screen.tx import ScreenPort
from librescreen.screen.text import WIDTHS, fit_name


class DisplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = Project(str(ROOT))
        cls.fonts = {}
        for role in ("t13", "t16", "t19", "d20", "d28", "d32"):
            cls.fonts[role] = hmi_font.FontReader((ROOT / "fonts" / ("font_%s.zi" % role)).read_bytes())

    def setUp(self):
        self.frames = []
        self.device = Device(self.project, self.frames.append, boot_frame=False)
        self.send("boot_logo.version.val=100")
        self.send("lang=2")
        self.send("page home")
        self.send("dim=100")
        self.frames.clear()

    def send(self, instruction):
        self.device.feed(instruction.encode("utf-8") + END)
        self.assertIsNone(self.device.last_error, instruction)

    def test_every_original_action_reaches_the_host(self):
        actions = {"light_btn": 0, "beep_btn": 1, "stop_btn": 2, "nozzle_btn": 3,
                   "bed_btn": 4, "chamber_btn": 5, "last_file_btn": 6,
                   "nav_main": 30, "nav_adjust": 31, "nav_files": 32, "nav_settings": 33,
                   "nozzle_temp": 3, "nozzle_set": 3, "nozzle_unit": 3, "last_file_name": 6}
        for name, action in actions.items():
            with self.subTest(name=name):
                self.frames.clear()
                self.device.tap(*self.device.center(name))
                self.assertEqual(b"".join(self.frames), bytes((0x65, ids.MAIN, action)) + END)
                self.assertIsNone(self.device.last_error)

    def test_version_warning_and_soc_conversion(self):
        warning = ("ver_panel", "ver_warning", "ui_ver_lbl", "ui_ver", "soc_ver_lbl", "soc_ver")
        for version, visible in ((100, False), (101, True), (100, False)):
            self.send("boot_logo.version.val=%d" % version)
            self.send("page home")
            self.assertEqual(self.device.attr("soc_ver", "txt"), str(version))
            states = {obj.name: obj for obj in self.device.objects()}
            for name in warning:
                self.assertEqual(states[name].visible, visible, name)

    def test_placeholders_and_fixed_geometry(self):
        for heater in ("nozzle", "bed", "chamber"):
            self.assertEqual(self.device.attr(heater + "_temp", "txt"), "---")
            self.assertEqual(self.device.attr(heater + "_set", "txt"), "/ ---")
            self.assertEqual(self.device.attr(heater + "_temp", "w"), 52)
        self.assertEqual(self.device.attr("last_file_pic", "w"), 140)
        self.assertEqual(self.device.attr("last_file_pic", "h"), 140)
        self.assertEqual(self.device.attr("last_file_pic", "vscope"), 1)

    def test_host_refresh_uses_only_real_attributes(self):
        port = ScreenPort()
        port._send = self.device.feed
        with patch.object(g, "port", port), \
             patch.object(file_list, "detect_disk", return_value=0), \
             patch.object(g.screen, "main_picture_refreshed", True), \
             patch.object(g.screen, "open_reprint_asked", True), \
             patch.multiple(g.klippy, extruder_temperature=31.6, extruder_target=220,
                            heater_bed_temperature=40, heater_bed_target=60,
                            hot_temperature=None, hot_target=0):
            home.main()
            self.assertIsNone(self.device.last_error)
            self.assertEqual(self.device.attr("nozzle_temp", "txt"), "32")
            self.assertEqual(self.device.attr("nozzle_set", "txt"), "/ 220")
            self.assertEqual(self.device.attr("chamber_temp", "txt"), "---")

    def test_cached_name_and_thumbnail_survive_return_to_home(self):
        self.send('last_file_name.txt="cached.gcode"')
        self.send('last_file_pic.write("cached-image")')
        before = dict(self.device.written)
        self.send("page filament")
        self.send("page home")
        port = ScreenPort()
        port._send = self.device.feed
        with patch.object(g, "port", port), \
             patch.object(file_list, "detect_disk", return_value=-1), \
             patch.object(g.screen, "main_picture_refreshed", True), \
             patch.object(g.screen, "main_picture_detected", True), \
             patch.object(g.screen, "open_reprint_asked", True):
            home.main()
        self.assertIsNone(self.device.last_error)
        self.assertEqual(self.device.attr("last_file_name", "txt"), "cached.gcode")
        self.assertEqual(self.device.written, before)
        self.assertTrue(next(obj for obj in self.device.objects() if obj.name == "last_file_pic").visible)

    def test_icon_update_does_not_paint_over_temperature(self):
        from librescreen.screen.faces import FACES
        self.send('nozzle_temp.txt="220"')
        before = Renderer(self.project).render(self.device)
        self.send("nozzle_icon.pic=" + FACES["nozzle_icon"]["on"][0])
        after = Renderer(self.project).render(self.device)
        self.assertEqual(before.crop((56, 250, 108, 290)).tobytes(), after.crop((56, 250, 108, 290)).tobytes())

    def test_wide_font_metrics_match_host(self):
        for name in ("часть_" * 30 + ".gcode", "模型" * 40 + ".gcode", "very_long_name_" * 20 + ".gcode"):
            for line in fit_name(name, 224).split("\\r"):
                glyphs = [self.fonts["t16"].glyph(ord(ch)) for ch in line]
                self.assertTrue(all(glyph is not None for glyph in glyphs), line)
                for ch, glyph in zip(line, glyphs):
                    self.assertEqual(WIDTHS[ord(ch)], glyph["width"], ch)
                self.assertLessEqual(sum(glyph["width"] for glyph in glyphs), 224)
        self.assertEqual(self.fonts["t16"].header["h"], 20)

    def test_digit_fonts_contain_dash_and_fit_the_slots(self):
        for role in ("d20", "d28", "d32"):
            self.assertIsNotNone(self.fonts[role].glyph(ord("-")))
        for value in ("---", "0", "350"):
            self.assertLessEqual(sum(self.fonts["d28"].glyph(ord(ch))["width"] for ch in value), 52)
        self.assertLessEqual(sum(self.fonts["t13"].glyph(ord(ch))["width"] for ch in "/ ---"), 34)

    def test_passive_pages_and_home_load_in_every_language(self):
        renderer = Renderer(self.project)
        self.send("boot_logo.version.val=101")     # Include the Home warning, not just its hidden normal state.
        for language in range(13):
            for page in ("boot_logo", "restart_needed", "shutting_down", "home"):
                with self.subTest(language=language, page=page):
                    self.send("lang=%d" % language)
                    self.send("page " + page)
                    renderer.render(self.device)
                    self.assertIsNone(self.device.last_error)
                    for obj in self.device.objects():
                        if obj.type != "text" or not obj.visible or not obj.attrs.get("txt"):
                            continue
                        a = obj.attrs
                        font = renderer.font(a["font"])
                        lines = renderer._wrap(a["font"], a["txt"], a["w"], a["spax"], a["isbr"])
                        self.assertLessEqual(len(lines) * (font.height + a["spay"]) - a["spay"], a["h"],
                                             "%s.%s: %s" % (page, obj.name, lines))
                        self.assertTrue(all(renderer._advance(a["font"], ch) is not None for ch in a["txt"]), obj.name)


if __name__ == "__main__":
    unittest.main()
