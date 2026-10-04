"""The bed screws pages take the screw positions from [bed_screws] of the Klipper config."""
import logging
import unittest

from librescreen import state as g
from librescreen.moonraker import printer_status
from support import IsolatedState


def configfile(**screws):
    return {"settings": {"bed_screws": screws}}


class BedScrewsTest(IsolatedState):
    def test_the_defaults_are_the_stock_screws(self):
        self.assertEqual(g.levelling.bed_screws, [(10.0, 10.0), (230.0, 10.0), (125.0, 240.0)])

    def test_the_screws_come_from_the_config(self):
        printer_status.parse_configfile(configfile(screw1=[12.0, 11.0], screw2=[228.0, 11.0],
                                                   screw3=[125.0, 238.0], screw4=[10.0, 240.0]))
        self.assertEqual(g.levelling.bed_screws, [(12.0, 11.0), (228.0, 11.0), (125.0, 238.0)])

    def test_a_text_value_is_read_too(self):
        printer_status.parse_configfile(configfile(screw1="5, 6"))
        self.assertEqual(g.levelling.bed_screws[0], (5.0, 6.0))

    def test_a_missing_or_broken_screw_keeps_its_default(self):
        with self.assertLogs(printer_status.log, logging.WARNING):
            printer_status.parse_configfile(configfile(screw1=[12.0, 11.0], screw2="x"))
        self.assertEqual(g.levelling.bed_screws, [(12.0, 11.0), (230.0, 10.0), (125.0, 240.0)])

    def test_no_bed_screws_section_changes_nothing(self):
        printer_status.parse_configfile({"settings": {}})
        self.assertEqual(g.levelling.bed_screws, [(10.0, 10.0), (230.0, 10.0), (125.0, 240.0)])


if __name__ == "__main__":
    unittest.main()
