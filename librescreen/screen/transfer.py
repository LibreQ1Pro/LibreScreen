"""Transfer of the pictures of the file list (jpg) to the screen RAM.

The TJC screen accepts files with the ``twfile`` instruction followed by data
frames: 12 byte header + payload + 2 byte CRC.  The screen answers 0x05 for
every frame that was written successfully, 0x04 on failure and 0x24 when its
buffer overflows (those bytes are picked up by ui.parse_cmd_msg_from_tjc_screen
and stored in the get_0x?? flags).
"""

import logging
import time

from librescreen import state as g
from librescreen.screen import thumbnail
from librescreen.util import paths
from librescreen.util.guard import run_guarded
from librescreen.util.cpp import to_string

log = logging.getLogger(__name__)

# BLOCK_SIZE 3072
BLOCK_SIZE = 3800
HEADER_SIZE = 12


def time_differ(duration, start_time):
    tmp = int(time.time())
    tmp = tmp - start_time
    if tmp > duration:
        return 1
    else:
        return 0


def time_differ_ms(duration, start_time):
    tmp = int(time.time() * 1000)
    tmp = tmp - start_time
    if tmp > duration:
        return 1
    else:
        return 0


def _send_list_pictures():
    """Sends the small pictures of the file list that the page asked for. The page is not refreshed meanwhile (4.4.22: refresh_page_show() waits while
    the pictures are sent); the touch (disabled by the page buttons of the file list) is enabled once at the end instead of around every picture."""
    g.pictures.begin_show_64_jpg = False
    g.pictures.send_jpg_status = True
    try:
        for i in range(6):
            if g.pictures.have_64_jpg[i]:
                time.sleep((50500 + i * 500) / 1e6)
                ram_path = "ram/file%d.jpg" % i
                if isinstance(g.pictures.have_64_png_path[i], thumbnail.GcodeRef):
                    # Python only: jpg made from the thumbnail inside the gcode file
                    log.debug("%s", g.pictures.have_64_png_path[i])
                    jpg_data = thumbnail.jpeg(g.pictures.have_64_png_path[i], thumbnail.LIST_SIZE)
                    if jpg_data is not None:
                        sent_jpg_to_tjc(ram_path, jpg_data)
                else:
                    jpg_path = paths.gcode_files() + "/" + g.pictures.have_64_png_path[i]
                    log.debug("%s", jpg_path)
                    sent_jpg_to_tjc(ram_path, jpg_path)
                g.pictures.have_64_jpg[i] = False
    finally:
        g.pictures.send_jpg_status = False         # whatever happened: the page has to be refreshed again
        g.port.tsw("255", "1")      # enable touch
        log.debug("Touch enabled")


def sent_jpg_thread_handle(arg=None):
    """Preview picture thread."""
    while True:
        if g.pictures.begin_show_64_jpg:
            run_guarded(_send_list_pictures)
        time.sleep(0.06)


def calccrc(crcbuf, crc):
    """CRC of a single byte"""
    crc = crc ^ crcbuf
    for i in range(8):
        chk = crc & 1
        crc = crc >> 1
        crc = crc & 0x7fff
        if chk == 1:
            crc = crc ^ 0xa001
        crc = crc & 0xffff
    return crc


def check_crc(buf, length):
    """CRC (Modbus) of a buffer, returned with the two bytes swapped"""
    crc = 0xFFFF
    for i in range(length):
        crc = calccrc(buf[i], crc)
    hi = crc % 256
    lo = crc // 256
    crc = (hi << 8) | lo
    return crc


def delete_small_jpg():
    """Delete all small preview pictures"""
    g.port.delfile("ram/file0.jpg")
    time.sleep(0.056)
    g.port.delfile("ram/file1.jpg")
    time.sleep(0.056)
    g.port.delfile("ram/file2.jpg")
    time.sleep(0.056)
    g.port.delfile("ram/file3.jpg")
    time.sleep(0.056)


def _frame_header(frame_id, length):
    """Header of a data frame of the pass-through transfer: ``length`` is the size of the data with the CRC."""
    return bytes([0x3A, 0xA1, 0xBB, 0x44, 0x7F, 0xFF, 0xFE, 0x01,
                  frame_id & 0xff, (frame_id >> 8) & 0xff, length & 0xff, (length >> 8) & 0xff])


# ends the pass-through mode
EXIT_FRAME = bytes([0x3A, 0xA1, 0xBB, 0x44, 0x7F, 0xFF, 0xFE, 0x00, 0xFF, 0xFF, 0x00, 0x00])


def _leave_pass_through(times):
    g.port.write(EXIT_FRAME)
    log.debug("%s", EXIT_FRAME.hex().upper())
    for _ in range(times - 1):
        g.port.write(EXIT_FRAME)


def _send_frame(frame_id, data):
    """Send one data frame (header, data, CRC) and wait until the screen has written it.

    Returns False when the transfer has to be given up (the pass-through mode is left then).
    """
    frame = bytearray(data)
    crc_val = check_crc(frame, len(frame))
    frame += bytes([(crc_val >> 8) & 0xff, crc_val & 0xff])
    header = _frame_header(frame_id, len(frame))
    g.port.write(header)
    g.port.write(frame)

    # 0x05 means the frame was written successfully
    start_time = int(time.time())
    resent_time = int(time.time() * 1000)
    g.update.get_0x05 = False
    g.update.get_0xfd = False
    g.update.get_0x04 = False
    while not g.update.get_0x05 and not g.update.get_0xfd:
        time.sleep(0.002)
        # 0x04 means the frame could not be written
        if g.update.get_0x04:
            _leave_pass_through(2)
            log.info("Got 0x04, failed")
            return False
        # re-send on timeout
        if time_differ_ms(800, resent_time) and not g.update.get_0x24:
            resent_time = int(time.time() * 1000)
            g.port.write(header)
            g.port.write(frame)
            log.info("Timed out waiting for the answer, re-sending the frame")

        if time_differ(4, start_time):
            _leave_pass_through(3)
            log.info("Timed out writing the data frame, failed")
            return False

        # CLL stop sending when the screen buffer overflows
        if g.update.get_0x24:
            time.sleep(4)
            g.update.get_0x24 = False
            return False
    return True


def sent_jpg_to_tjc(ram_path, jpg_path):
    """Send a picture (a file, or the bytes themselves) to the screen"""
    try:
        # (Python only: the picture can also be passed as bytes kept in memory)
        if isinstance(jpg_path, (bytes, bytearray)):
            data = bytes(jpg_path)
        else:
            with open(jpg_path, "rb") as f:
                data = f.read()
    except OSError:
        log.debug("Failed to open the file")
        return True

    # send the pass-through instruction
    g.port.twfile(ram_path, to_string(len(data)))
    # wait for 0xfe + terminator
    time.sleep(0.105)
    # send header + data frames until the end of the file
    payload_size = BLOCK_SIZE - HEADER_SIZE - 2         # keep two bytes for the CRC
    for frame_id, start in enumerate(range(0, len(data), payload_size)):
        if not _send_frame(frame_id & 0xffff, data[start:start + payload_size]):
            return False

    log.info("Picture written to the screen memory")
    return True
