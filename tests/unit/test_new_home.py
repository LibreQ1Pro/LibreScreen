"""The migrated Home contract. Run in the librescreen-port-test container, never on the host."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image

from librescreen import state as g
from librescreen.pages import home, file_list
from librescreen.screen import thumbnail
from librescreen.screen.text import fit_name, width
from librescreen.screen.tx import END
from support import PortRecorder

ROOT = Path(__file__).resolve().parents[2]


class HomeTest(PortRecorder):
    def strings(self):
        return [value[:-len(END)].decode("utf-8") for value in self.commands]

    def test_temperatures_targets_and_attributes_exist(self):
        home.main_heater("nozzle", 31.6, 220)
        home.main_heater("bed", 40, 0)
        home.main_heater("chamber", None, float("nan"))
        commands = self.strings()
        self.assertIn('nozzle_temp.txt="32"', commands)
        self.assertIn('nozzle_set.txt="/ 220"', commands)
        self.assertIn('bed_temp.txt="40"', commands)
        self.assertIn('bed_set.txt="/ 0"', commands)
        self.assertIn('chamber_temp.txt="---"', commands)
        self.assertIn('chamber_set.txt="/ ---"', commands)
        self.assertIn("nozzle_temp.pco=" + home.HOT, commands)
        self.assertIn("bed_temp.pco=" + home.TEXT, commands)
        page = json.loads((ROOT / "display_firmware/pages/home.json").read_text())
        attrs = {obj["key"]: obj["attributes"] for obj in page["objects"]}
        for command in commands:
            obj, attribute = command.split("=", 1)[0].split(".")
            self.assertIn(attribute, attrs[obj], command)

    def test_unknown_readings_are_not_zero(self):
        for value in (None, "", "not a number", float("inf"), float("nan")):
            self.assertEqual(home.temperature(value), "---")
        self.assertEqual(home.temperature(350), "350")
        self.assertEqual(home.temperature(0), "0")

    def test_no_cached_file_hides_and_clears_the_picture(self):
        with patch.object(file_list, "refresh_page_files"), patch.object(g.files, "list_last_printed", ""):
            home.main_last_file_picture()
        self.assertIn("vis last_file_pic,0", self.strings())
        self.assertIn("last_file_pic.close()", self.strings())
        self.assertIn('last_file_name.txt=""', self.strings())
        self.assertFalse(g.screen.main_picture_detected)

    def test_thumbnail_geometry_and_unshortened_file_name(self):
        name = "very_long_part_name_" * 12 + ".gcode"
        with patch.object(file_list, "refresh_page_files"), \
             patch.object(g.files, "list_last_printed", "box/" + name), \
             patch.object(thumbnail, "find", return_value=object()), \
             patch.object(file_list, "send_file_picture", return_value=True) as send:
            home.main_last_file_picture()
        send.assert_called_once_with(thumbnail.GcodeRef("box/" + name), 140, "last_file_pic",
                                     matte=(41, 40, 41), background=(49, 48, 57), radius=12)
        shown = file_list.shown_name(name)           # without ".gcode"
        self.assertFalse(shown.endswith(".gcode"))
        self.assertIn('last_file_name.txt="' + fit_name(shown, 224, lines=2) + '"', self.strings())
        self.assertTrue(g.screen.main_picture_detected)

    def test_baud_is_restored_if_thumbnail_write_raises(self):
        with patch.object(thumbnail, "colpic", return_value="image"), \
             patch.object(file_list.time, "sleep"), \
             patch.object(file_list.widgets, "send_chunks_cp", side_effect=RuntimeError("write failed")):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                file_list.send_file_picture(thumbnail.GcodeRef("part.gcode"), 140, "last_file_pic", matte=home.THUMB_MATTE)
        self.assertEqual(self.strings()[-1], "baud=115200")


class NamesTest(unittest.TestCase):
    def test_two_lines_keep_extension_and_fit_real_font(self):
        for name in ("part.gcode", "часть_" * 60 + ".gcode", "模型" * 100 + ".gcode",
                     "א" * 100 + ".gcode", "unbroken" * 100 + ".gcode", "ß" * 200 + ".gcode"):
            result = fit_name(name, 224)
            self.assertTrue(result.endswith(".gcode"), result)
            lines = result.split("\\r")
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(width(line), 224, line)
            if len(name) > 60:
                self.assertIn("…", result)

    def test_ssid_is_not_treated_as_a_file(self):
        result = fit_name("very_long_network_name_" * 20 + ".gcode", 100, lines=1, extension=False)
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(width(result), 100)

    def test_unsupported_glyphs_and_commands(self):
        result = fit_name('abc";page 15\n\\r😃.gcode', 224)
        self.assertNotIn('"', result)
        self.assertNotIn("\n", result)
        self.assertNotIn("😃", result)
        self.assertIn("?", result)
        self.assertEqual(fit_name("é.gcode", 224), "é.gcode")


class ThumbnailTest(unittest.TestCase):
    def test_alpha_and_round_corners_are_prepared_on_the_host(self):
        source = Image.new("RGBA", (160, 80), (255, 0, 0, 0))
        result = thumbnail.prepare_picture(source, 140, home.THUMB_MATTE, 12, home.THUMB_BACKGROUND)
        self.assertEqual(result.size, (140, 140))
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.getpixel((0, 0)), home.THUMB_MATTE)
        self.assertEqual(result.getpixel((70, 70)), home.THUMB_BACKGROUND)
        source.putpixel((80, 40), (255, 255, 255, 255))
        result = thumbnail.prepare_picture(source, 140, home.THUMB_MATTE, 12, home.THUMB_BACKGROUND)
        self.assertNotEqual(result.getpixel((70, 70)), home.THUMB_BACKGROUND)


if __name__ == "__main__":
    unittest.main()
