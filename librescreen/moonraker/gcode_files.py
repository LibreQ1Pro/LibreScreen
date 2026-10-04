"""The gcode file list of the file pages and the metadata of the chosen file."""

import logging
import sys

from librescreen import state as g
from librescreen.config import runtime
from librescreen.moonraker.http_client import send_request
from librescreen.moonraker.json_fields import read_fields
from librescreen.screen import navigation, pageids as ids
from librescreen.util import paths
from librescreen.util.cpp import (c_int,
                            f32,
                            find_last_of,
                            jeq,
                            jfloat,
                            jget,
                            jint,
                            jpath,
                            jsize,
                            json_dump,
                            json_parse,
                            jstr,
                            substr,
                            to_string)

log = logging.getLogger(__name__)


def file_name_of(path):
    return path[path.rfind("/") + 1:]


def parse_file_estimated_time(response):
    result = jget(response, "result")
    read_fields(g.files, result, [("meta_estimated_time", "estimated_time", lambda v: c_int(jfloat(v))),
                                  ("meta_filename", "filename", jstr),
                                  ("meta_filament_total", "filament_total", lambda v: f32(jint(v))),
                                  ("meta_object_height", "object_height", jint),
                                  ("meta_filament_name", "filament_name", jstr),
                                  ("meta_filament_type", "filament_type", jstr),
                                  ("meta_filament_weight_total", "filament_weight_total", jfloat),
                                  ("meta_gimage", "gimage", jstr),
                                  ("meta_simage", "simage", jstr)])
    thumbnails = jget(result, "thumbnails")
    for i in range(jsize(thumbnails)):
        thumb = jget(thumbnails, i)
        if jeq(jget(thumb, "width"), 168) or jeq(jget(thumb, "width"), 300):
            g.files.thumbnail_relative_path = jstr(jget(thumb, "relative_path"))
            directory = parent_directory(g.files.meta_filename)
            if directory == "":
                g.files.thumbnail_path = g.files.thumbnail_relative_path
            else:
                g.files.thumbnail_path = directory + "/" + g.files.thumbnail_relative_path
            log.info("Picture path %s", g.files.thumbnail_path)
            break
    g.files.meta_parse_finished = True


def last_printed_file():
    """The file that was printed last, from the print history of Moonraker: its path under gcodes/ (``dir/name.gcode``), or "" when there is none (the
    newest job whose file still exists; a cancelled or a failed print counts as well)."""
    import json
    response = send_request(runtime.cfg.moonraker_host, runtime.cfg.moonraker_port, "server/history/list?limit=20&order=desc", "GET")
    try:
        jobs = json.loads(response)["result"]["jobs"]
    except (ValueError, KeyError, TypeError):
        return ""
    for job in jobs:
        name = job.get("filename") or ""
        if job.get("exists") and name.endswith(".gcode") and not name.startswith("."):
            return name
    return ""


def get_page_files_filelist(current_dir):
    """Fetch the file list information"""
    if g.files.list_last_printing_files_dir == current_dir:
        g.files.list_is_last_print_files_dir = True
    else:
        g.files.list_is_last_print_files_dir = False
    g.files.list_dirname_list.clear()
    g.files.list_filename_list.clear()
    g.files.list_dirname_filename_list.clear()
    g.files.list_modified = {}
    json_temp = None
    result = None
    # the last printed file (from the history of Moonraker) is shown on Home, not in the list
    g.files.list_last_printed = last_printed_file() if g.files.list_folder_layers == 0 else g.files.list_last_printed
    json_files_directory = send_request(runtime.cfg.moonraker_host, runtime.cfg.moonraker_port, "server/files/directory?path=" + current_dir, "GET")
    if json_files_directory != "":
        json_temp = json_parse(json_files_directory)
        result = jget(json_temp, "result")

    for i in range(jsize(jget(result, "dirs"))):
        temp_dirname = jstr(jpath(result, "dirs", i, "dirname"))
        if temp_dirname != "System Volume Information" and temp_dirname.find(".") != 0 and temp_dirname != "sda1":
            g.files.list_dirname_list.add(temp_dirname)

    for j in range(jsize(jget(result, "files"))):
        log.debug("%s", json_dump(jpath(result, "files", j, "filename")))
        temp_filename = jstr(jpath(result, "files", j, "filename"))
        if temp_filename.find(".gcode") != -1:
            if temp_filename.find(".") != 0:
                g.files.list_filename_list.add(temp_filename)
                g.files.list_modified[temp_filename] = jfloat(jpath(result, "files", j, "modified"))

    for name in sorted_std(g.files.list_dirname_list):
        g.files.list_dirname_filename_list.add("[d] " + name)

    for name in sorted_std(g.files.list_filename_list):
        g.files.list_dirname_filename_list.add("[f] " + name)

    count = len(g.files.list_dirname_filename_list)
    if 0 == count % 4:      # CLL the divisor is the number of files on one page
        g.files.list_pages = count // 4 - 1
        if g.files.list_pages <= 0:
            g.files.list_pages = 0
    else:
        g.files.list_pages = count // 4


def sorted_std(strings):
    """Iteration order of std::set<std::string> (byte-wise lexicographic)."""
    from librescreen.util.cpp import s2b
    return sorted(strings, key=s2b)


def entry_order(entry):
    """The order of the list: the folders A-Z, then the files, the newest first (the time they were added)."""
    kind, name = substr(entry, 0, 3), substr(entry, 4)
    if kind == "[d]":
        return (0, 0.0, name.casefold(), name)
    return (1, -g.files.list_modified.get(name, 0.0), name.casefold(), name)


def set_page_files_show_list(pages):
    g.files.list_list_name[0] = ""
    g.files.list_list_name[1] = ""
    g.files.list_list_name[2] = ""
    g.files.list_list_name[3] = ""

    entries = sorted(g.files.list_dirname_filename_list, key=entry_order)
    it = 0

    for i in range(pages * 4):
        it += 1
        # NOTE: the original dereferences the iterator even past the end (UB)
        if it < len(entries):
            log.debug("%s", entries[it])
    for i in range(4):
        if it < len(entries):
            g.files.list_list_name[i] = entries[it]
            it += 1

    # test output
    for j in range(4):
        if g.files.list_list_name[j] != "":
            g.files.list_list_show_type[j] = substr(g.files.list_list_name[j], 0, 3)
            g.files.list_list_show_name[j] = substr(g.files.list_list_name[j], 4)
        else:
            g.files.list_list_show_type[j] = "[n]"
            g.files.list_list_show_name[j] = ""


def open_last_printed():
    """The preview of the file that was printed last (the button of Home)."""
    from librescreen.pages import file_list
    g.screen.jump_print = False
    g.screen.show_preview_complete = False
    g.screen.cache_clicked = True
    g.files.list_path_stack.append(g.files.list_path)
    g.files.list_print_files_path = "/" + g.files.list_last_printed
    g.files.list_folder_layers += 1
    file_list.get_file_estimated_time(substr(g.files.list_print_files_path, 1))
    navigation.page_to(ids.PREVIEW)


def get_sub_dir_files_list(button):
    from librescreen.pages import file_list
    from librescreen.printer import job
    if "[d]" == g.files.list_list_show_type[button]:
        g.files.list_path_stack.append(g.files.list_path)
        g.files.list_path = g.files.list_path + "/" + g.files.list_list_show_name[button]
        g.files.list_folder_layers += 1
        navigation.page_to(ids.FILE_LIST)
        g.files.list_current_pages = 0
        g.screen.file_list_refreshed = False       # 4.4.22
        file_list.refresh_page_files(g.files.list_current_pages)
        file_list.refresh_files_list()
    elif "[f]" == g.files.list_list_show_type[button]:
        g.screen.jump_print = False
        g.screen.show_preview_complete = False
        g.screen.cache_clicked = False
        g.files.list_path_stack.append(g.files.list_path)
        g.files.list_print_files_path = g.files.list_path + "/" + g.files.list_list_show_name[button]
        g.files.list_folder_layers += 1
        log.info("%s", substr(g.files.list_print_files_path, 1))
        file_list.get_file_estimated_time(substr(g.files.list_print_files_path, 1))
        job.check_timelapse_state()       # 4.4.22 timelapse switch of the preview page
        navigation.page_to(ids.PREVIEW)


def get_parenet_dir_files_list():
    from librescreen.pages import file_list
    from librescreen.printer import klipper
    # NOTE: std::stack::top() on an empty stack is undefined behaviour in C++
    g.files.list_previous_path = g.files.list_path_stack[-1] if g.files.list_path_stack else ""
    g.files.list_path = g.files.list_previous_path
    if g.screen.page != ids.PREVIEW:
        g.screen.file_list_refreshed = False       # 4.4.22 (back from the preview: keep the list)
        g.files.list_current_pages = 0
    # 4.4.2 CLL local / USB buttons on the file list page
    if file_list.detect_disk() == -1 and g.screen.file_mode == "USB":
        navigation.page_to(ids.FILE_LIST)
        g.files.list_pages = 0
        g.files.list_current_pages = 0
        g.files.list_folder_layers = 1
        g.files.list_previous_path = ""
        g.files.list_root_path = "gcodes/"
        g.files.list_path = "/sda1"
        file_list.refresh_page_files(g.files.list_current_pages)
        file_list.refresh_files_list()
        klipper.get_object_status()
    elif g.files.list_folder_layers > 0:
        navigation.page_to(ids.FILE_LIST)
        g.files.list_folder_layers -= 1
        if g.files.list_folder_layers == 0:
            file_list.refresh_page_files(g.files.list_current_pages)
            file_list.refresh_files_list()
            g.files.list_previous_path = ""
            g.files.list_path = ""
        else:
            file_list.refresh_page_files(g.files.list_current_pages)
            file_list.refresh_files_list()
            if g.files.list_path_stack:
                g.files.list_path_stack.pop()


def parse_file_estimated_time_send(response):
    if jget(response, "estimated_time") is not None:
        g.files.meta_estimated_time = c_int(jfloat(jget(response, "estimated_time")))
    if jget(response, "filename") is not None:
        g.files.meta_filename = jstr(jget(response, "filename"))
    if jget(response, "filament_total") is not None:
        g.files.meta_filament_total = f32(jint(jget(response, "filament_total")))
        log.info("Filament length %f", g.files.meta_filament_total)
    if jget(response, "object_height") is not None:
        g.files.meta_object_height = jint(jget(response, "object_height"))
    if jget(response, "filament_name") is not None:
        g.files.meta_filament_name = jstr(jget(response, "filament_name"))
    if jget(response, "filament_type") is not None:
        g.files.meta_filament_type = jstr(jget(response, "filament_type"))

    if jget(response, "filament_weight_total") is not None:
        g.files.meta_filament_weight_total = jfloat(jget(response, "filament_weight_total"))
    if jget(response, "gimage") is not None:
        g.files.meta_gimage = jstr(jget(response, "gimage"))
        log.info("gimage")
    if jget(response, "simage") is not None:
        g.files.meta_simage = jstr(jget(response, "simage"))
        log.info("simage")
    thumbnails = jpath(response, "result", "thumbnails")
    if thumbnails is not None:
        last = _json_back(thumbnails)
        if last is not None:
            g.files.thumbnail_relative_path = jstr(jget(last, "relative_path"))
            if parent_directory(g.files.meta_filename) == "":
                g.files.thumbnail_path = g.files.thumbnail_relative_path
            else:
                g.files.thumbnail_path = parent_directory(g.files.meta_filename) + "/" + g.files.thumbnail_relative_path
            log.info("Picture path %s", g.files.thumbnail_path)
    else:
        g.files.thumbnail_relative_path = ""
        g.files.thumbnail_path = ""
    g.files.meta_parse_finished = True


def _json_back(value):
    """json::back(): last element of an array / object, the value itself otherwise."""
    if isinstance(value, list):
        return value[-1] if value else None
    if isinstance(value, dict):
        if not value:
            return None
        return value[sorted(value)[-1]]
    return value


def parent_directory(path):
    found = find_last_of(path, "/\\")
    if found != -1:
        return substr(path, 0, found)
    else:
        return ""   # no separator: root directory


def output_imgdata(thumbpath, size):
    """Converts a thumbnail into the screen's ColPic text format.

    The original runs QIDI's colpic.py and libColPic.so; both are re-implemented in
    colpic.py of this package.  The result is kept in memory (``g.pictures.tjc_data``).  A failed conversion
    leaves None there (the original keeps the previous file and shows the
    picture of another file).
    """
    from librescreen.screen import colpic
    from librescreen.screen import thumbnail
    g.pictures.tjc_data = None
    if isinstance(thumbpath, thumbnail.GcodeRef):
        # Python only: picture from the thumbnails inside the gcode file
        log.debug("%s", "Converting the thumbnail of " + thumbpath + " (" + to_string(size) + ")")
        try:
            g.pictures.tjc_data = thumbnail.colpic(thumbpath, size)
        except Exception as e:
            sys.stderr.write("gene4: %s: %s\n" % (type(e).__name__, e))
        return 0
    if size != 176:
        path = paths.gcode_files() + "/" + thumbpath
    else:
        path = thumbpath
    log.debug("Converting the thumbnail %s (%s)", path, to_string(size))
    try:
        g.pictures.tjc_data = colpic.encode_picture(path, size)
    except Exception as e:
        # the original script dies with a traceback (the old output stays)
        sys.stderr.write("gene4: %s: %s\n" % (type(e).__name__, e))
    return 0
