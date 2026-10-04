"""The host side of the new screen design: what the pages ask the screen for exists, and the values are what the widgets expect.
Nothing of the printer is touched (the port records the instructions)."""
import os
import sys
import unittest
from unittest.mock import patch

from librescreen import state as g
from librescreen.pages import file_list, guide, preview, widgets
from librescreen.screen import events, thumbnail
from librescreen.screen.faces import FACES
from support import IsolatedState, PortRecorder as Recorder

TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "display_firmware", "tools")


class ReadoutTest(Recorder):
    def test_heater_row_sets_the_fields_the_colour_and_the_icon(self):
        widgets.heater_row("nozzle", 31.6, 220)
        widgets.heater_row("bed", 25, 0)
        sent = self.sent()
        self.assertIn('nozzle_temp.txt="32"', sent)
        self.assertIn('nozzle_set.txt="/ 220"', sent)
        self.assertIn("nozzle_temp.pco=" + widgets.HOT, sent)
        self.assertIn("bed_temp.pco=" + widgets.TEXT, sent)
        on, off = FACES["nozzle_icon"]["on"][0], FACES["bed_icon"]["off"][0]
        self.assertIn("nozzle_icon.pic=" + on, sent)
        self.assertIn("bed_icon.pic=" + off, sent)

    def test_fan_values_are_percent_integers(self):
        with patch.multiple(g.klippy, out_pin_fan0_value=0.3, out_pin_fan2_value=0.555, out_pin_fan3_value=1.0):
            widgets.fan_values()
        self.assertEqual([c for c in self.sent() if "_val" in c], ['fan1_val.txt="30"', 'fan2_val.txt="56"', 'fan3_val.txt="100"'])

    def test_readout_can_be_shown_and_hidden(self):
        widgets.show_readout("nozzle", True)
        widgets.show_readout("nozzle", False)
        self.assertEqual(self.sent(), ["vis nozzle_temp,1", "vis nozzle_set,1", "vis nozzle_unit,1", "vis nozzle_temp,0", "vis nozzle_set,0", "vis nozzle_unit,0"])

    def test_the_setup_step_waits_for_the_temperature(self):
        cases = ((100, 220, False), (205, 220, False), (215, 220, True), (230, 220, True), (30, 0, False), (180, 190, True), (170, 190, False))
        for current, target, ready in cases:
            self.commands.clear()
            self.port.forget()
            with patch.multiple(g.klippy, extruder_temperature=current, extruder_target=target):
                guide.open_filament_video_2()
            sent = self.sent()
            self.assertIn("next.pic=" + FACES["next"]["ready" if ready else "wait"][0], sent, (current, target))
            self.assertIn("tsw next,%d" % ready, sent, (current, target))
            self.assertIn("cur_val.val=%d" % round(current), sent)
            self.assertIn("tar_val.val=%d" % round(target), sent)


class PreviewTest(Recorder):
    def test_the_pictures_have_the_size_of_their_widgets(self):
        sizes = []

        def fake(path, size, matte=None, radius=0, background=None):
            sizes.append((size, matte, radius, background))
            return "data%d" % size
        sent = []
        with patch.object(thumbnail, "colpic", fake), patch.object(preview, "send_chunks_txt", lambda data, target="cp_data": sent.append((target, data))), \
             patch.object(preview, "send_chunks_cp", lambda widget, data: sent.append((widget, data))), \
             patch.object(preview, "fast_screen_link"), patch.object(preview.calibration, "bed_leveling_switch"), patch.object(g.screen, "jump_print", False):
            self.assertTrue(preview.send_preview_pictures(thumbnail.GcodeRef("part.gcode")))
        self.assertEqual([s[0] for s in sizes], [132, 72, 152])
        self.assertTrue(all(s[1] == preview.PAGE_COLOUR and s[2] == 12 and s[3] == preview.CARD_COLOUR for s in sizes))
        self.assertEqual(sent, [("cp_data", "data132"), ("cp_data_s", "data72"), ("preview_pic", "data152")])

    def test_a_print_that_is_running_needs_the_small_pictures_only(self):
        with patch.object(thumbnail, "colpic", lambda path, size, **k: "d%d" % size), patch.object(preview, "send_chunks_txt"), \
             patch.object(preview, "send_chunks_cp") as big, patch.object(preview, "fast_screen_link"), patch.object(g.screen, "jump_print", True):
            self.assertTrue(preview.send_preview_pictures(thumbnail.GcodeRef("part.gcode")))
        big.assert_not_called()

    def test_a_missing_thumbnail_is_not_an_exception(self):
        def missing(path, size, **k):
            raise IOError("no thumbnail")
        with patch.object(thumbnail, "colpic", missing):
            self.assertFalse(preview.send_preview_pictures(thumbnail.GcodeRef("part.gcode")))


class ValueFramesTest(Recorder):
    def test_targets_are_echoed_as_text_with_the_slash(self):
        with patch.object(events.heating, "set_extruder_target"), patch.object(events.settings, "set_extruder_target"):
            events.tjc_event_setted_handler(events.ids.PRINTING, events.ids.PRINTING_EXTRUDER, 220 & 255, 220 >> 8)
        self.assertIn('nozzle_set.txt="/ 220"', self.sent())

    def test_a_fan_value_of_the_filament_page_returns_to_the_page(self):
        with patch.object(events.heating, "set_fan0") as fan, patch.object(events, "page_to") as page:
            events.tjc_event_setted_handler(events.ids.FILAMENT, events.ids.FILAMENT_SET_FAN_1, 250, 0)
        fan.assert_called_once_with(100)                # capped
        page.assert_called_once_with(events.ids.FILAMENT)


class FileListTest(Recorder):
    def test_a_name_is_cut_to_its_slot_and_the_tabs_are_one_widget(self):
        names = ["Benchy.gcode", "x" * 200 + ".gcode", "模型" * 50 + ".gcode", "d"]
        with patch.object(g.files, "list_list_show_name", names), patch.object(g.files, "list_list_show_type", ["[f]", "[f]", "[f]", "[d]"]), \
             patch.object(file_list, "detect_disk", return_value=0), patch.object(file_list, "detect_disk_2", return_value=1), \
             patch.object(g.screen, "file_list_refreshed", True), patch.object(g.screen, "file_mode", "Local"), \
             patch.object(g.files, "list_current_pages", 0), patch.object(g.files, "list_pages", 0), patch.object(g.files, "list_folder_layers", 0):
            file_list.refresh_files_list()
        sent = self.sent()
        self.assertIn("tabs_seg.pic=" + FACES["tabs_seg"]["local"][0], sent)
        for number in "1234":
            line = next(c for c in sent if c.startswith("file%s_name.txt=" % number))
            self.assertLessEqual(len(line), 400)
        self.assertTrue(next(c for c in sent if c.startswith("file2_name.txt=")).count("…") == 1)


class FileListSlotsTest(Recorder):
    def refresh(self, types, mode="Local", disk=1):
        names = ["a.gcode", "b", "c.gcode", "d.gcode"]
        with patch.object(g.files, "list_list_show_name", names), patch.object(g.files, "list_list_show_type", types), \
             patch.object(file_list, "detect_disk", return_value=0 if disk == 1 else -1), patch.object(file_list, "detect_disk_2", return_value=disk), \
             patch.object(g.screen, "file_list_refreshed", True), patch.object(g.screen, "file_mode", mode), \
             patch.object(g.files, "list_current_pages", 0), patch.object(g.files, "list_pages", 0), patch.object(g.files, "list_folder_layers", 0):
            file_list.refresh_files_list()
        return self.sent()

    def test_only_a_file_has_a_placeholder_and_a_thumbnail(self):
        sent = self.refresh(["[f]", "[d]", "[f]", "[n]"])
        self.assertIn("vis file1_pic,1", sent)
        self.assertIn("vis file2_pic,0", sent)
        self.assertIn("vis file2_pic_bg,0", sent)
        self.assertIn("vis file4_name,0", sent)
        self.assertIn("vis file2_name,1", sent)

    def test_no_drive_says_empty_in_the_language_of_the_screen(self):
        sent = self.refresh(["[n]"] * 4, mode="USB", disk=-1)
        self.assertIn("vis empty_msg,1", sent)
        self.assertFalse([c for c in sent if c.startswith("empty_msg.txt")])        # the text is the one the page set for its language

    def test_a_list_with_files_has_no_empty_message(self):
        sent = self.refresh(["[f]", "[n]", "[n]", "[n]"])
        self.assertIn("vis empty_msg,0", sent)

    def test_the_selected_tab_is_white_and_the_other_is_muted(self):
        sent = self.refresh(["[f]", "[n]", "[n]", "[n]"], mode="USB")
        self.assertIn("usb_tab_lbl.pco=65535", sent)
        self.assertIn("local_tab_lbl.pco=42294", sent)


class SegmentedTest(Recorder):
    def test_the_selected_label_is_white(self):
        widgets.segmented("dist_seg", (("d01", "dist_01_lbl"), ("d1", "dist_1_lbl"), ("d10", "dist_10_lbl")), "d1")
        sent = self.sent()
        self.assertIn("dist_seg.pic=" + FACES["dist_seg"]["d1"][0], sent)
        self.assertIn("dist_1_lbl.pco=65535", sent)
        self.assertIn("dist_01_lbl.pco=42294", sent)
        self.assertIn("dist_10_lbl.pco=42294", sent)


class ListRowTest(Recorder):
    def test_a_blank_row_hides_its_text(self):
        widgets.list_row("row3", "blank")
        widgets.list_row("row1", "item")
        sent = self.sent()
        self.assertIn("vis row3_txt,0", sent)
        self.assertIn("vis row1_txt,1", sent)


class TemperatureFromHomeTest(Recorder):
    def test_a_heater_tile_opens_the_keyboard_in_its_mode_and_the_value_returns_home(self):
        from librescreen.clicks import printing
        with patch.object(printing, "page_to") as page:
            printing.main(events.ids.MAIN, events.ids.MAIN_SET_TEMP_2)
        page.assert_called_once_with(events.ids.FILAMENT_KB)
        self.assertIn("sys1=1", self.sent())
        self.assertTrue(g.screen.temperature_from_main)
        with patch.object(events.heating, "set_heater_bed_target"), patch.object(events.settings, "set_heater_bed_target"), patch.object(events, "page_to") as page:
            events.tjc_event_setted_handler(events.ids.FILAMENT, events.ids.FILAMENT_SET_HEATERBED, 60, 0)
        page.assert_called_once_with(events.ids.MAIN)
        self.assertFalse(g.screen.temperature_from_main)


class NetworkInfoTest(Recorder):
    def show(self, wifi, lan, radio=True):
        from librescreen.pages import connections
        reports = {"wifi": wifi, "ethernet": lan}
        with patch.object(connections.network, "device_report", side_effect=lambda kind: reports[kind]), \
             patch.object(connections.network, "wifi_radio", return_value=radio):
            connections.show_info()
        return self.sent()

    def test_values_that_are_not_known_are_dashes_and_the_interfaces_are_named(self):
        sent = self.show({"name": "wlx40a5ef2378f6", "state": "disconnected", "ip": "", "gateway": "", "mac": "", "ssid": ""},
                         {"name": "eth0", "state": "disconnected", "ip": "", "gateway": "", "mac": "", "ssid": ""})
        for line in ('wifi_if.txt="wlx40a5ef2378f6"', 'wifi_ssid.txt="---"', 'wifi_ip.txt="---"', 'wifi_gw.txt="---"',
                     'lan_if.txt="eth0"', 'lan_ip.txt="---"', 'lan_gw.txt="---"'):
            self.assertIn(line, sent)

    def test_a_connected_interface_shows_its_values(self):
        sent = self.show({"name": "wlan0", "state": "connected", "ip": "192.168.1.5", "gateway": "192.168.1.1", "mac": "", "ssid": "Home"},
                         {"name": "eth0", "state": "connected", "ip": "10.0.0.2", "gateway": "10.0.0.1", "mac": "", "ssid": ""})
        for line in ('wifi_ssid.txt="Home"', 'wifi_ip.txt="192.168.1.5"', 'lan_ip.txt="10.0.0.2"', 'lan_gw.txt="10.0.0.1"'):
            self.assertIn(line, sent)
        self.assertIn("radio_btn.pic=" + FACES["radio_btn"]["on"][0], sent)

    def test_a_switched_off_radio_shows_no_wifi_values(self):
        sent = self.show({"name": "wlan0", "state": "connected", "ip": "192.168.1.5", "gateway": "x", "mac": "", "ssid": "Home"},
                         {"name": "eth0", "state": "disconnected", "ip": "", "gateway": "", "mac": "", "ssid": ""}, radio=False)
        self.assertIn('wifi_ssid.txt="---"', sent)
        self.assertIn("radio_btn.pic=" + FACES["radio_btn"]["off"][0], sent)


class KnownNetworkTest(Recorder):
    SAVED = {"name": "Home", "uuid": "u1", "ssid": "Home", "autoconnect": True, "active": False, "stamp": 1}

    def click(self, ssid):
        from librescreen.clicks import system
        from librescreen.pages import connections
        g.net.wifi_ssid_list = [ssid, "", "", "", ""]
        g.screen.wifi_ssid_button_enabled[0] = True
        with patch.object(connections.network, "saved_wifi", return_value=[self.SAVED]), \
             patch.object(connections, "open_detail") as detail, patch.object(connections, "open_keyboard") as keyboard:
            system.wifi_list(events.ids.WIFI_LIST, events.ids.WIFI_LIST_SSID_1)
        return detail, keyboard

    def test_a_saved_network_opens_its_page(self):
        detail, keyboard = self.click("Home")
        detail.assert_called_once_with(self.SAVED, "list")
        keyboard.assert_not_called()

    def test_a_new_network_asks_for_the_password(self):
        detail, keyboard = self.click("Cafe")
        detail.assert_not_called()
        keyboard.assert_called_once()

    def test_forgetting_a_network_returns_to_the_list_it_was_opened_from(self):
        from librescreen.pages import connections
        connections.S.sel, connections.S.origin = self.SAVED, "list"
        with patch.object(connections.network, "forget"), patch("librescreen.pages.wifi.go_to_network") as back, patch.object(connections, "open_saved") as saved:
            connections.confirm_clicked(1)
        back.assert_called_once()
        saved.assert_not_called()


class LastPrintedTest(IsolatedState):
    def last(self, response):
        from librescreen.moonraker import gcode_files
        with patch.object(gcode_files, "send_request", return_value=response):
            return gcode_files.last_printed_file()

    def test_the_newest_job_whose_file_still_exists(self):
        history = '{"result": {"count": 3, "jobs": [{"filename": "gone.gcode", "exists": false}, {"filename": "box/a.gcode", "exists": true, "status": "cancelled"}, {"filename": "b.gcode", "exists": true}]}}'
        self.assertEqual(self.last(history), "box/a.gcode")

    def test_no_history_or_an_error_is_no_last_file(self):
        self.assertEqual(self.last(""), "")
        self.assertEqual(self.last("not json"), "")
        self.assertEqual(self.last('{"result": {"count": 0, "jobs": []}}'), "")
        self.assertEqual(self.last('{"error": {"code": 404}}'), "")


class FileOrderTest(IsolatedState):
    def order(self, entries, modified):
        from librescreen.moonraker import gcode_files
        with patch.object(g.files, "list_modified", modified):
            return sorted(entries, key=gcode_files.entry_order)

    def test_folders_a_to_z_then_files_newest_first(self):
        entries = ["[f] old.gcode", "[d] beta", "[f] new.gcode", "[d] Alpha", "[f] mid.gcode"]
        modified = {"old.gcode": 100.0, "mid.gcode": 200.0, "new.gcode": 300.0}
        self.assertEqual(self.order(entries, modified),
                         ["[d] Alpha", "[d] beta", "[f] new.gcode", "[f] mid.gcode", "[f] old.gcode"])

    def test_files_added_at_the_same_time_are_by_name(self):
        entries = ["[f] b.gcode", "[f] a.gcode"]
        self.assertEqual(self.order(entries, {"a.gcode": 5.0, "b.gcode": 5.0}), ["[f] a.gcode", "[f] b.gcode"])


class HostNamesTest(unittest.TestCase):
    def test_every_widget_the_host_writes_to_exists(self):
        sys.path.insert(0, TOOLS)
        try:
            import check_host_names
            self.assertEqual(check_host_names.problems(), [])
        finally:
            sys.path.remove(TOOLS)


if __name__ == "__main__":
    unittest.main()
