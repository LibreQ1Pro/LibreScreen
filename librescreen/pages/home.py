"""The Home page of the new screen design."""

import logging

from librescreen import state as g
from librescreen.pages import file_list
from librescreen.pages.widgets import temperature, two_state_button
from librescreen.printer import job
from librescreen.screen import thumbnail
from librescreen.screen.text import fit_name

log = logging.getLogger(__name__)

TEXT = "63422"       # #f4f4f7 in RGB565
HOT = "64459"        # #ff7a59 in RGB565
THUMB_SIZE = 140
THUMB_MATTE = (41, 40, 41)
THUMB_BACKGROUND = (49, 48, 57)


def main_heater(heater, current, target):
    active = temperature(target) not in ("---", "0")
    g.port.txt(heater + "_temp", temperature(current))
    g.port.txt(heater + "_set", "/ " + temperature(target))
    g.port.pco(heater + "_temp", HOT if active else TEXT)
    # Change only the icon: replacing the whole card would erase the overlaid text on the real TJC.
    g.port.face(heater + "_icon", "on" if active else "off")


def main_last_file_picture():
    """The first entry of the file list is the last printed file, if there is one."""
    g.files.list_pages = 0
    g.files.list_current_pages = 0
    g.files.list_folder_layers = 0
    g.files.list_previous_path = ""
    g.files.list_root_path = file_list.DEFAULT_DIR
    g.files.list_path = ""
    file_list.refresh_page_files(g.files.list_current_pages)
    g.port.vis("last_file_pic", "0")
    g.port.cp_close("last_file_pic")
    g.screen.main_picture_detected = False
    if not g.files.list_last_printed:
        g.port.face("last_file_btn", "noimg")
        g.port.txt("last_file_name", "")
        return

    name = file_list.shown_name(file_list.file_name_only(g.files.list_last_printed))
    picture_path = thumbnail.GcodeRef(g.files.list_last_printed)
    log.info("Picture path:%s", picture_path)
    thumb = thumbnail.find(picture_path, THUMB_SIZE, "PNG")
    g.port.face("last_file_btn", "noimg" if thumb is None else "photo")
    g.port.txt("last_file_name", fit_name(name, 224, lines=2))
    if thumb is None:
        return
    g.screen.main_picture_detected = file_list.send_file_picture(
        picture_path, THUMB_SIZE, "last_file_pic", matte=THUMB_MATTE,
        background=THUMB_BACKGROUND, radius=12)


def main():
    main_heater("nozzle", g.klippy.extruder_temperature, g.klippy.extruder_target)
    main_heater("bed", g.klippy.heater_bed_temperature, g.klippy.heater_bed_target)
    main_heater("chamber", g.klippy.hot_temperature, g.klippy.hot_target)

    g.port.face("usb_icon", "on" if file_list.detect_disk() == 0 else "off")
    g.port.face("lan_icon", "on" if g.net.lan_connected else "off")
    g.port.face("wifi_icon", "on" if g.net.status_result.wpa_state == "COMPLETED" else "off")
    two_state_button("light_btn", g.klippy.caselight_value != 0)
    two_state_button("beep_btn", g.klippy.out_pin_beep_value != 0)

    if not g.screen.main_picture_refreshed:
        main_last_file_picture()
        g.screen.main_picture_refreshed = True
    g.port.vis("last_file_pic", "1" if g.screen.main_picture_detected else "0")

    if not g.screen.open_reprint_asked:
        job.check_print_interrupted()
        g.screen.open_reprint_asked = True
