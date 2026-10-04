import glob
import json
import os
import unittest

from librescreen import state as g
from librescreen.pages import connections
from librescreen.screen import events, navigation

PAGES = os.path.join(os.path.dirname(__file__), "..", "..", "display_firmware", "pages")


class LanguageTest(unittest.TestCase):
    """The language is kept on the screen only (``lang``, EEPROM); the port follows what the screen reports."""

    def test_frame_sets_the_language_of_the_port(self):
        events.parse_cmd_msg_from_tjc_screen(bytes([navigation.LANGUAGE_FRAME, 1]).ljust(4096, b"\0"))
        self.assertEqual(g.config.language_status, 1)
        self.assertEqual(connections.tr("cancel"), "Отмена")
        events.parse_cmd_msg_from_tjc_screen(bytes([navigation.LANGUAGE_FRAME, 2]).ljust(4096, b"\0"))
        self.assertEqual(connections.tr("cancel"), "Cancel")

    def test_every_language_button_reports_the_choice(self):
        """Each page event that sets ``lang`` sends the frame ``a0 lang ff ff ff`` before it leaves the page."""
        report = ["prints 0xa0,1", "prints lang,1", "prints 0xff,1", "prints 0xff,1", "prints 0xff,1"]
        found = 0
        for path in glob.glob(os.path.join(PAGES, "*.json")):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for block in _blocks(json.loads(text)):
                if any(line.startswith("lang=") for line in block):
                    found += 1
                    at = block.index("wepo lang,100")
                    self.assertEqual(block[at + 1:at + 1 + len(report)], report, path)
        self.assertEqual(found, 26)         # 13 languages on the language and on the guide pages


def _blocks(o):
    if isinstance(o, list) and o and all(isinstance(x, str) for x in o):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _blocks(v)
    elif isinstance(o, list):
        for v in o:
            yield from _blocks(v)


if __name__ == "__main__":
    unittest.main()
