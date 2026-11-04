import unittest

from librescreen.screen import navigation as ui


class UiVersionTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(ui.version_number((0, 1, 0)), 100)
        self.assertEqual(ui.version_number((1, 7, 10)), 10710)
        self.assertEqual(ui.version_number((99, 99, 99)), 999999)

    def test_part_out_of_range(self):
        for version in ((0, 100, 0), (0, 0, 100), (100, 0, 0), (0, -1, 0)):
            with self.assertRaises(ValueError):
                ui.version_number(version)

    def test_screen_expects_the_same_number(self):
        """display_firmware/pages/home.json compares boot_logo.version with the number of ui.VERSION."""
        import json
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "..", "display_firmware", "pages", "home.json")
        with open(path, encoding="utf-8") as f:
            load = json.load(f)["root"]["events"]["codesload"]
        self.assertIn("if(boot_logo.version.val==%s)" % ui.UI_VERSION, load)


if __name__ == "__main__":
    unittest.main()
