import json
import os
import unittest

from librescreen.util import netstrings

PAGES = os.path.join(os.path.dirname(__file__), "..", "..", "display_firmware", "pages")


class NetStringsTest(unittest.TestCase):
    def test_every_text_has_every_language(self):
        for key, row in netstrings.TEXT.items():
            self.assertEqual(len(row), len(netstrings.LANGUAGES), key)
            self.assertTrue(all(row), key)

    def test_order_matches_the_screen(self):
        self.assertEqual(netstrings.LANGUAGES[0], "zh")
        self.assertEqual(netstrings.LANGUAGES[1], "ru")
        self.assertEqual(netstrings.LANGUAGES[2], "en")

    def test_text_by_language(self):
        self.assertEqual(netstrings.text("cancel", 1), "Отмена")
        self.assertEqual(netstrings.text("cancel", 2), "Cancel")

    def test_unknown_language_is_english(self):
        self.assertEqual(netstrings.text("cancel", 99), "Cancel")
        self.assertEqual(netstrings.text("cancel", -1), "Cancel")

    def test_pages_of_the_screen_use_the_table(self):
        """tools/net_i18n.py has been run: the pages carry the texts of the table."""
        with open(os.path.join(PAGES, "network_info.json"), encoding="utf-8") as f:
            code = "\n".join(json.load(f)["root"]["events"]["codesload"])
        for text in netstrings.TEXT["network"]:
            self.assertIn('title.txt="%s"' % text, code)


if __name__ == "__main__":
    unittest.main()


class HostTextsExistTest(unittest.TestCase):
    def test_every_text_the_host_asks_for_is_in_the_table(self):
        """A key that is missing raises KeyError in the handler of a touch, the button does nothing (it was the "Hidden" button of the Wi-Fi list)."""
        import re
        root = os.path.join(os.path.dirname(__file__), "..", "..", "librescreen")
        asked = set()
        for folder, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        asked.update(re.findall(r'\btr\("([a-z_]+)"\)', f.read()))
        self.assertTrue(asked)
        self.assertEqual(sorted(asked - set(netstrings.TEXT)), [])
