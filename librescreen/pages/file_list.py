"""The file list pages and their pictures, the USB drive."""

import glob
import logging
import os
import shutil
import time

from librescreen import state as g
from librescreen.moonraker import gcode_files
from librescreen.moonraker.gcode_files import output_imgdata
from librescreen.moonraker.rpc_requests import json_get_gcode_metadata
from librescreen.pages import widgets
from librescreen.printer import klipper
from librescreen.screen import pageids as ids, thumbnail
from librescreen.screen.text import fit_name
from librescreen.screen.navigation import page_to
from librescreen.screen.transfer import delete_small_jpg
from librescreen.util import paths
from librescreen.util.cpp import substr, to_string

log = logging.getLogger(__name__)


DEFAULT_DIR = "gcodes/"
NAME_WIDTH = 112            # the width of the name of a file slot of the screen, in pixels of the wide font
LIST_PICTURE = thumbnail.LIST_SIZE          # the thumbnails of the slots are 112 x 112 (the card colour and the round corners are in the picture)


def file_name_only(path):
    return substr(path, path.rfind("/") + 1)


def name_of(path):
    """File name without the directories"""
    return substr(path, path.rfind("/") + 1)


# entry type of the list -> look of its row
ROW_LOOKS = {
    "[d]": "dir",
    "[f]": "file",
    "[n]": "none",          # no drive
}


def nav_button(button, disabled):
    """The page / folder buttons look different when there is nothing to go to."""
    g.port.face(button, "off" if disabled else "on")


def queue_list_pictures():
    """CLL refresh the pictures after all the other widgets: the picture thread sends them."""
    for i in range(4):
        g.pictures.have_64_jpg[i] = False
        g.pictures.have_64_png_path[i] = ""
        t = g.files.list_list_show_type[i]
        if t == "[f]":
            name = g.files.list_list_show_name[i]
            # NOTE: the original sends <dir>/.thumbs/<name>-112x112_QD.jpg (made only
            # by QIDI's slicer / Moonraker) to the screen; the port takes the
            # thumbnail from the gcode file itself (see thumbnail.py).
            picture_path = thumbnail.GcodeRef(substr(g.files.list_path + "/" + name, 1))
            log.info("Picture path:%s", picture_path)
            if thumbnail.find(picture_path, LIST_PICTURE, "JPEG") is not None:
                g.pictures.have_64_jpg[i] = True
                g.pictures.have_64_png_path[i] = picture_path
        # the picture thread also enables the touch again when there is no picture
        g.pictures.begin_show_64_jpg = True


def shown_name(name):
    """The name of a slot without ``.gcode`` (Python only: every file of the list is one, and the width of the slot is better spent on the name)."""
    return name[:-6] if name.lower().endswith(".gcode") and len(name) > 6 else name


def refresh_files_list():
    # 4.4.22: the pictures are only sent again when the list changed
    # (file_list_refreshed), the folder and page are kept meanwhile
    if not g.screen.file_list_refreshed:
        delete_small_jpg()
    for i in range(4):
        row = "file" + to_string(i + 1)
        g.port.txt(row + "_name", fit_name(shown_name(g.files.list_list_show_name[i]), NAME_WIDTH, lines=1))
        t = g.files.list_list_show_type[i]
        if t in ROW_LOOKS:
            g.port.face(row, ROW_LOOKS[t])
        shown = "1" if t == "[f]" else "0"          # the placeholder and the thumbnail belong to a file only
        g.port.vis(row + "_pic_bg", shown)
        g.port.vis(row + "_pic", shown)
        g.port.vis(row + "_name", "1" if t != "[n]" else "0")      # the box of a name is the colour of the card: nothing to show without a slot

    # 4.4.2 CLL local / USB buttons on the file list page
    mode = "local" if g.screen.file_mode == "Local" else "usb"
    widgets.segmented("tabs_seg", (("local", "local_tab_lbl"), ("usb", "usb_tab_lbl")), mode)
    # "Empty" (the text is set by the screen in its language) when there is nothing to show: no drive, or an empty folder
    empty = all(t == "[n]" for t in g.files.list_list_show_type[:4])
    if g.screen.file_mode == "USB" and (detect_disk_2() != 1 or detect_disk() == -1):
        empty = True
    g.port.vis("empty_msg", "1" if empty else "0")
    nav_button("prev", g.files.list_current_pages == 0)
    nav_button("next", g.files.list_current_pages == g.files.list_pages)
    nav_button("up_dir", g.files.list_folder_layers == 0
                or (g.files.list_folder_layers == 1 and g.screen.file_mode != "Local"))
    if g.screen.file_list_refreshed:
        g.port.tsw("255", "1")      # pictures still in the screen memory: enable touch
    else:
        queue_list_pictures()
        g.screen.file_list_refreshed = True


def refresh_page_files(page_index):
    gcode_files.get_page_files_filelist(g.files.list_root_path + g.files.list_path)
    gcode_files.set_page_files_show_list(page_index)


def get_file_estimated_time(filename):
    g.ep.send(json_get_gcode_metadata(filename))


def clear_cp0_image():
    g.port.cp_close("file_preview.preview_pic")
    g.port.txt("file_preview.cp_data", "")
    g.port.txt("file_preview.cp_data_s", "")
    g.port.txt("file_preview.cp_pad", "")
    g.screen.show_preview_gimage_completed = False
    g.files.meta_parse_finished = False
    g.files.meta_simage = ""
    g.files.meta_gimage = ""


def is_mounted(path):
    """4.4.22: 1 if path is a mount point, 0 if not, -1 on errors."""
    try:
        return 1 if os.stat("/").st_dev != os.stat(path).st_dev else 0
    except FileNotFoundError:
        return 0            # no drive was ever mounted here: that is no error
    except OSError as e:
        log.error("is_mounted %s: %s", path, str(e))
        return -1


def detect_disk_2():
    """4.4.22: is the USB drive mounted (1), not mounted (0), or missing (-1)?"""
    result = is_mounted(paths.gcode_files() + "/sda1")
    if result == 1:
        log.info("%s is mounted", paths.gcode_files() + "/sda1")
    elif result == 0:
        log.info("%s is not mounted", paths.gcode_files() + "/sda1")
    return result


def detect_disk():
    """0 if a USB drive is mounted in the gcode directory (``sda1``, see contrib/usb-automount), -1 if not."""
    return 0 if is_mounted(paths.gcode_files() + "/sda1") == 1 else -1


def go_to_file_list():
    # 4.4.22: the folder and page are kept while the list is up to date
    if g.screen.file_mode == "Local":
        page_to(ids.FILE_LIST)
        if not g.screen.file_list_refreshed:
            g.files.list_pages = 0
            g.files.list_current_pages = 0
            g.files.list_folder_layers = 0
            g.files.list_previous_path = ""
            g.files.list_root_path = DEFAULT_DIR
            g.files.list_path = ""
        refresh_page_files(g.files.list_current_pages)
        refresh_files_list()
        klipper.get_object_status()
    else:
        page_to(ids.FILE_LIST)
        if not g.screen.file_list_refreshed:
            g.files.list_pages = 0
            g.files.list_current_pages = 0
            g.files.list_folder_layers = 1
            g.files.list_previous_path = ""
            g.files.list_root_path = DEFAULT_DIR
            g.files.list_path = "/sda1"
        refresh_page_files(g.files.list_current_pages)
        refresh_files_list()
        klipper.get_object_status()
        # the label "Setup Guide" is set by the screen itself (common_set: a timer, the text in the screen language)


def print_log():
    """CLL export the logs to the USB drive"""
    if detect_disk() == -1:
        page_to(ids.PRINT_LOG_F)    # CLL no USB drive: tell the user the export failed
    else:
        target = paths.gcode_files() + "/sda1/QD_Log"
        os.makedirs(target, exist_ok=True)
        for name in ("klippy.log", "moonraker.log"):       # and the rotated ones (klippy.log.2024-01-01)
            for source in glob.glob(glob.escape(paths.klipper_logs() + "/" + name) + "*"):
                try:
                    shutil.copy(source, target)
                except OSError as e:
                    log.error("%s: %s", source, e)
        page_to(ids.PRINT_LOG_S)


def send_file_picture(path, pixel, obj, matte=None, radius=0, background=None):
    """Send a ColPic into the current page. New pages prepare its size and matte on the host."""
    g.files.meta_simage = ""
    g.files.meta_gimage = ""
    g.files.meta_parse_finished = False
    if matte is None:
        output_imgdata(path, pixel)
        data = g.pictures.tjc_data
    else:
        try:
            data = thumbnail.colpic(path, pixel, matte=matte, radius=radius, background=background)
        except (OSError, ValueError) as error:
            log.error("Could not prepare thumbnail: %s", error)
            data = None
    if data is None:
        log.error("No converted picture")
        g.screen.show_preview_complete = True
        return False
    g.files.meta_gimage = data
    g.port.baud(921600)
    time.sleep(0.01)
    g.port.set_baud(921600)
    try:
        g.port.cp_close(obj)
        if g.files.meta_gimage != "":
            log.debug("Sending the file picture")
            widgets.send_chunks_cp(obj, g.files.meta_gimage)
    finally:
        g.port.baud(115200)
        time.sleep(0.01)
        g.port.set_baud(115200)
    g.port.vis(obj, "1")
    return True
