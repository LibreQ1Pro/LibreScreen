"""The keyboards clamp a target to max_temp of the heaters of the Klipper config."""
import unittest
from unittest.mock import patch

from librescreen import state as g
from librescreen.moonraker import printer_status
from librescreen.screen import events
from support import IsolatedState


def configfile(**sections):
    return {"settings": {name.replace("heater_generic_", "heater_generic "): {"max_temp": value}
                         for name, value in sections.items()}}


class MaxTempsTest(IsolatedState):
    def test_the_defaults_are_the_stock_limits(self):
        self.assertEqual((g.limits.extruder, g.limits.heater_bed, g.limits.chamber), (350, 120, 60))

    def test_the_config_sets_the_limits(self):
        printer_status.parse_configfile(configfile(extruder=300.0, heater_bed=110.0, heater_generic_chamber=65.0))
        self.assertEqual((g.limits.extruder, g.limits.heater_bed, g.limits.chamber), (300, 110, 65))

    def test_a_missing_or_wrong_value_keeps_the_limit(self):
        printer_status.parse_configfile({"settings": {"extruder": {"max_temp": "x"}, "heater_bed": {}}})
        self.assertEqual((g.limits.extruder, g.limits.heater_bed, g.limits.chamber), (350, 120, 60))

    def test_a_keyboard_value_is_clamped_to_the_limit(self):
        printer_status.parse_configfile(configfile(extruder=300.0))
        with patch.object(events.heating, "set_extruder_target") as apply, patch.object(events.settings, "set_extruder_target"), \
             patch.object(events, "page_to"):
            events.SETTED[(events.ids.FILAMENT, events.ids.FILAMENT_SET_EXTRUDER)](999)
        apply.assert_called_once_with(300)


if __name__ == "__main__":
    unittest.main()
