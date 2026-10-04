"""The preview page of a file (details, thumbnail, pop-ups)."""

import logging
import time

from librescreen import state as g
from librescreen.pages import file_list
from librescreen.pages.widgets import cut_after_point, fast_screen_link, send_chunks_cp, send_chunks_txt, two_state_button
from librescreen.printer import calibration, job
from librescreen.screen import pageids as ids, thumbnail
from librescreen.screen.text import POPUP_MSG_LINES, POPUP_MSG_WIDTH, fit_name, wrap_text
from librescreen.screen.navigation import page_to
from librescreen.util.cpp import f32, substr, to_string

log = logging.getLogger(__name__)


PREVIEW_PICTURE = 152       # the pictures the host makes for the widgets: exactly their size, with the card colour and the round corners in the pixels
PRINT_PICTURE = 132         # the print pages (cp_data)
KEYBOARD_PICTURE = 72       # the number keyboard of the print pages (cp_data_s)
PAGE_COLOUR = (24, 24, 24)
CARD_COLOUR = (49, 48, 57)


def picture_data(path, size):
    """The ColPic text of the thumbnail of ``path`` for a widget of ``size``; raises OSError / ValueError when there is no usable thumbnail."""
    return thumbnail.colpic(path, size, matte=PAGE_COLOUR, radius=12, background=CARD_COLOUR)


def preview_details():
    # 4.4.2 CLL only the file name is shown on the preview page (cut to a line of the slot)
    g.port.txt("file_name", fit_name(file_list.shown_name(file_list.file_name_only(g.files.meta_filename)), 248, lines=1))
    if g.files.meta_estimated_time:
        g.port.txt("est_time", job.show_time(g.files.meta_estimated_time))
    else:
        g.port.txt("est_time", "---")

    if g.files.meta_filament_weight_total:
        temp = to_string(g.files.meta_filament_weight_total)
        g.port.txt("fil_weight", cut_after_point(temp, 2) + " g")
    else:
        g.port.txt("fil_weight", "---")

    if g.files.meta_filament_total:
        temp = to_string(f32(g.files.meta_filament_total / 1000))
        g.port.txt("fil_length", cut_after_point(temp, 2) + " m")
    else:
        g.port.txt("fil_length", "---")

    if g.files.meta_filament_type != "":
        g.port.txt("fil_type", g.files.meta_filament_type)
    elif g.files.meta_filament_name != "":
        g.port.txt("fil_type", g.files.meta_filament_name)
    else:
        g.port.txt("fil_type", "---")


def preview_picture_ref():
    """The gcode file with the thumbnail of the file, or "" when there is none.

    NOTE: the original looks for <dir>/.thumbs/<name>-160x160.png, then .jpg, made by QIDI's Moonraker; the port
    reads the thumbnail from the gcode file itself (see thumbnail.py): nothing is written to the file system.
    """
    if g.screen.jump_print:
        candidates = ["/" + g.klippy.print_stats_filename]
    elif g.screen.cache_clicked:
        candidates = ["/" + g.files.meta_filename]            # the last printed file: the path Moonraker gave
        g.screen.cache_clicked = False
    else:
        candidates = [job.stack_top(g.files.list_path_stack) + "/" + file_list.name_of(g.files.meta_filename)]
    for candidate in candidates:
        candidate = substr(candidate, 1)
        log.info("picture_path:%s", candidate)
        if thumbnail.find(candidate, 160, "PNG") is not None:
            return thumbnail.GcodeRef(candidate)
    return ""


def send_preview_pictures(picture_path):
    """Send the pictures to the screen: the two small ones (the print pages and their keyboard) and the big one of this page;
    False when the picture could not be converted."""
    try:
        small = {target: picture_data(picture_path, size) for target, size in (("cp_data", PRINT_PICTURE), ("cp_data_s", KEYBOARD_PICTURE))}
        big = None if g.screen.jump_print else picture_data(picture_path, PREVIEW_PICTURE)
    except (OSError, ValueError) as error:
        log.error("No converted picture: %s", error)
        return False
    g.files.meta_simage = small["cp_data"]
    g.port.txt("file_preview.cp_pad", "")
    for target, data in small.items():
        g.port.txt("file_preview." + target, "")
        with fast_screen_link():
            log.debug("Sending the small picture %s", target)
            send_chunks_txt(data, target)

    # big picture
    if big is not None:
        g.files.meta_gimage = big
        with fast_screen_link():
            g.port.cp_close("file_preview.preview_pic")
            log.debug("Sending the big picture")
            send_chunks_cp("preview_pic", big)
        calibration.bed_leveling_switch(True)
    return True


def preview():
    # 4.4.22: pictures of the 4.4.24 screen, timelapse switch b3
    two_state_button("level_btn", g.screen.bed_leveling)
    two_state_button("timelapse_btn", g.screen.timelapse_enabled)
    if not g.files.meta_parse_finished or g.screen.show_preview_complete:
        return

    preview_details()
    picture_path = preview_picture_ref()
    log.debug("Picture path:%s", picture_path)
    if picture_path != "" and not g.screen.show_preview_gimage_completed:
        if not send_preview_pictures(picture_path):
            g.screen.show_preview_complete = True
            return
        g.screen.show_preview_gimage_completed = True

    g.port.vis("preview_pic", "1" if g.screen.show_preview_gimage_completed else "0")

    g.screen.show_preview_complete = True
    if g.screen.jump_print:
        job.check_filament_type()
        g.screen.jump_print = False


def clear_preview():
    g.files.meta_filename = ""
    g.files.meta_estimated_time = 0
    g.files.meta_filament_weight_total = 0.0
    g.files.meta_filament_name = ""
    g.files.meta_filament_type = ""
    g.files.meta_simage = ""
    g.files.meta_gimage = ""


def preview_pop():
    # 4.4.2 support mates and hall filament width sensors
    if not g.klippy.filament_detected:
        time.sleep(1)
        job.set_print_pause()
        page_to(ids.PRINT_NO_FILAMENT)
    if g.klippy.print_stats_state == "standby":
        page_to(ids.PRINT_STOPPING)
    if g.klippy.print_stats_state == "error":
        page_to(ids.GCODE_ERROR)
        job.cancel_print()
        job.clear_previous_data()
        g.port.txt("msg", wrap_text("G-code error: " + g.screen.error_message, POPUP_MSG_WIDTH, POPUP_MSG_LINES))
