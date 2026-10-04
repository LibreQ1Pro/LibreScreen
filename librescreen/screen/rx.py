"""Receiving from the screen: the byte stream of the serial port is cut into frames in a thread of its own.

Every frame the screen sends ends with ``ff ff ff`` (``display_firmware/tools/lint_frames.py`` checks the project for
it). Reading in the main loop - which also draws the pages and runs the handlers, and waits for the port on every
instruction it sends - handled one frame per read and lost the others; here the port is read all the time and the
frames wait in a queue until the main loop takes them.
"""

import os
import queue
import select
import time


END = b"\xff\xff\xff"

# frames that are cut by their length instead of the first terminator: the data of ``71 page widget low high`` is a
# number of two bytes, which may be 0xff 0xff (-1) and then ends in ``ff ff ff ff ff``. The other frames are cut at the
# first terminator (the click frames of the firmware are ``65 page widget``, the ones of the editor ``65 page id event``).
FIXED = {0x71: 5}
ACK = 0x05              # the answer to a data packet of the picture transfer / of the screen flashing is this single byte
STALE_AFTER = 0.1       # s, an unfinished frame that got no new byte for that long is dropped
MAX_BUFFER = 8192       # bytes, something is wrong when a frame is longer
MAX_AGE = 5.0           # s, a frame that waited longer in the queue is dropped: the page it was meant for is gone


class FrameParser:
    """``feed(bytes)`` -> the complete frames (without the terminator) that the bytes finished."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._buf = bytearray()
        self._seen = 0.0
        self.dropped = 0        # unfinished / oversized pieces thrown away

    def feed(self, data=b""):
        now = self._clock()
        if data:
            self._buf += data
            self._seen = now
        elif self._buf and now - self._seen > STALE_AFTER:
            self.dropped += 1
            self._buf.clear()
            return []
        frames = []
        while self._buf:
            frame = self._take()
            if frame is None:
                break
            if frame:
                frames.append(bytes(frame))
        if len(self._buf) > MAX_BUFFER:
            self.dropped += 1
            self._buf.clear()
        return frames

    def _take(self):
        """The next frame (b"" for an empty one), or None when more bytes are needed."""
        buf = self._buf
        if buf[0] == ACK:               # one byte, no terminator (with one it is "invalid font id", handled alike)
            del buf[:1]
            return b"\x05"
        size = FIXED.get(buf[0])
        if size is not None:
            if len(buf) < size + 3:
                return None             # (the bytes in between may be data, wait for the rest)
            if buf[size:size + 3] == END:
                frame = buf[:size]
                del buf[:size + 3]
                return frame
        end = buf.find(END)
        if end < 0:
            return None
        frame = buf[:end]
        del buf[:end + 3]
        return frame


def reader_thread(fd, parser, frames):
    """Runs forever: reads the port, puts ``(time, frame)`` into the queue ``frames``."""
    while True:
        try:
            ready = select.select([fd], [], [], 0.05)[0]
            data = os.read(fd, 4096) if ready else b""
        except (BlockingIOError, InterruptedError):
            data = b""
        except OSError:
            time.sleep(0.1)
            continue
        now = time.monotonic()
        for frame in parser.feed(data):
            frames.put((now, frame))


def next_frame(frames, timeout):
    """The oldest frame of the queue that is still current, or None after ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            received, frame = frames.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            return None
        if time.monotonic() - received <= MAX_AGE:
            return frame
        if time.monotonic() >= deadline:
            return None
