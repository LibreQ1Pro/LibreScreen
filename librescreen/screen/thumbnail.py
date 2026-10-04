"""Thumbnails read on the fly from the gcode files (Python only, not in the original).

The original looks for pictures that QIDI's Moonraker extracts next to the
files (``/home/mks/gcode_files/<dir>/.thumbs/<name>-160x160.png`` and the
``-112x112_QD.jpg`` made only by QIDI's slicer), converts them with
colpic.py into /home/mks/tjc and sends the jpg files to the screen.  That only
works with QIDI's own software and file layout.

The port reads the thumbnails embedded in the gcode itself instead.  The start of
the file is downloaded from Moonraker (``/server/files/gcodes/<path>`` with an
HTTP Range header) until all thumbnail blocks have been seen::

    ; thumbnail begin 160x160 12345        (PNG, PrusaSlicer / OrcaSlicer / QIDI Studio / Cura)
    ; thumbnail_JPG begin 112x112 6789     (JPEG)
    ; thumbnail_QOI begin 96x96 1234       (QOI, only if Pillow can read it)
    ; <base64>
    ; thumbnail end

Everything stays in memory: no .thumbs directory, no intermediate files.
"""

import base64
import io
import re
import sys
import threading
import time
import urllib.request

from librescreen.config import runtime


CHUNK_SIZE = 256 * 1024             # bytes downloaded per request
READ_LIMIT = 4 * 1024 * 1024        # thumbnails further into the file are ignored
CACHE_SECONDS = 10.0                # one page refresh looks up and then converts
CACHE_ENTRIES = 16

_BEGIN = re.compile(r"^;\s*(thumbnail(?:_JPG|_PNG|_QOI)?) begin (\d+)x(\d+)(?: (\d+))?")
_END = re.compile(r"^;\s*thumbnail(?:_JPG|_PNG|_QOI)? end")
_FORMATS = {"thumbnail": "PNG", "thumbnail_PNG": "PNG", "thumbnail_JPG": "JPEG", "thumbnail_QOI": "QOI"}

_cache = {}
_cache_lock = threading.Lock()


class GcodeRef(str):
    """A gcode path (relative to the gcodes root) used in place of a picture
    file path: the picture is taken from the thumbnails inside the file."""


class Thumbnail(object):
    __slots__ = ("fmt", "width", "height", "data")

    def __init__(self, fmt, width, height, data):
        self.fmt = fmt
        self.width = width
        self.height = height
        self.data = data

    def __repr__(self):
        return "<%s %dx%d %d bytes>" % (self.fmt, self.width, self.height, len(self.data))


def _log(text):
    sys.stderr.write("thumbnail: %s\n" % text)


def _fetch(path, start, end):
    """Bytes start..end (inclusive) of a gcode file; b"" past the end, None on error."""
    url = runtime.cfg.moonraker_url("server/files/gcodes/" + urllib.parse.quote(path))
    req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (start, end)})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200 and start > 0:
                # the server ignored the Range header and sends the whole file
                return resp.read(end + 1)[start:]
            return resp.read(end - start + 1)
    except urllib.error.HTTPError as e:
        if e.code == 416:       # range not satisfiable: past the end of the file
            return b""
        _log("%s: HTTP %d" % (path, e.code))
        return None
    except Exception as e:
        _log("%s: %s" % (path, e))
        return None


def _parse(path):
    """All thumbnails found at the start of the gcode file."""
    thumbs = []
    block = None                # [fmt, w, h, base64 lines] of the open block
    pending = ""                # incomplete last line of the previous chunk
    offset = 0
    while offset < READ_LIMIT:
        chunk = _fetch(path, offset, offset + CHUNK_SIZE - 1)
        if chunk is None:
            return thumbs
        offset += len(chunk)
        last = len(chunk) < CHUNK_SIZE
        lines = (pending + chunk.decode("latin-1")).split("\n")
        pending = "" if last else lines.pop()
        for raw in lines:
            line = raw.strip()
            if block is not None:
                if _END.match(line):
                    try:
                        data = base64.b64decode("".join(block[3]))
                        thumbs.append(Thumbnail(block[0], block[1], block[2], data))
                    except (ValueError, TypeError):
                        _log("%s: broken %dx%d thumbnail" % (path, block[1], block[2]))
                    block = None
                elif line.startswith(";"):
                    block[3].append(line[1:].strip())
                continue
            m = _BEGIN.match(line)
            if m:
                block = [_FORMATS[m.group(1)], int(m.group(2)), int(m.group(3)), []]
            elif line and not line.startswith(";"):
                # the first gcode command: the slicers write the thumbnails
                # into the header, so there are none further down
                return thumbs
        if last:
            break
    return thumbs


def get_thumbnails(path):
    """Thumbnails of a gcode file (cached for a few seconds)."""
    now = time.time()
    with _cache_lock:
        hit = _cache.get(path)
        if hit is not None and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    thumbs = _parse(path)
    with _cache_lock:
        if len(_cache) >= CACHE_ENTRIES:
            del _cache[min(_cache, key=lambda k: _cache[k][0])]
        _cache[path] = (now, thumbs)
    return thumbs


def _readable(thumb):
    if thumb.fmt != "QOI":
        return True
    try:
        from PIL import Image
        Image.open(io.BytesIO(thumb.data)).load()
        return True
    except Exception:
        return False


def choose(thumbs, size, prefer_fmt):
    """The thumbnail to show at ``size`` pixels: an exact size×size one in the
    preferred format, then any exact one, then the smallest that is at least
    as big, then the biggest one."""
    thumbs = [t for t in thumbs if _readable(t)]
    if not thumbs:
        return None
    exact = [t for t in thumbs if t.width == size and t.height == size]
    for t in exact:
        if t.fmt == prefer_fmt:
            return t
    if exact:
        return exact[0]
    bigger = [t for t in thumbs if t.width >= size and t.height >= size]
    if bigger:
        return min(bigger, key=lambda t: t.width * t.height)
    return max(thumbs, key=lambda t: t.width * t.height)


def choose_sharpest(thumbs):
    """The thumbnail to scale down: the biggest one (a PNG before a JPEG of the same size): scaling a big picture down is sharper than scaling a small one."""
    thumbs = [t for t in thumbs if _readable(t)]
    if not thumbs:
        return None
    return max(thumbs, key=lambda t: (t.width * t.height, t.fmt == "PNG"))


def find(path, size, prefer_fmt):
    """The thumbnail of the gcode file to show at ``size`` pixels, or None."""
    return choose(get_thumbnails(path), size, prefer_fmt)


def _screen_image(thumb, turn=True):
    """The thumbnail as a PIL image turned for the screen: the screen is mounted
    rotated, so the pictures are sent turned 90 degrees counterclockwise (the
    .thumbs pictures of QIDI's Moonraker are stored that way already); the big
    ColPic pictures (``turn=False``) are sent as they are."""
    from PIL import Image
    image = Image.open(io.BytesIO(thumb.data))
    image.load()
    if not turn:
        return image
    return image.transpose(getattr(Image, "Transpose", Image).ROTATE_90)


def _flatten(image):
    """RGB image with the transparent parts black, like the screen's background
    (Python only: colpic.py drops the alpha channel and shows whatever colour
    the slicer left under the transparent pixels)."""
    from PIL import Image
    if image.mode in ("RGBA", "LA", "P", "PA"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (0, 0, 0))
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def prepare_picture(image, size, matte, radius=0, background=None):
    """A square thumbnail with its alpha and rounded corners already composited for ColPic."""
    from PIL import Image, ImageDraw, ImageOps
    if size <= 0 or radius < 0 or radius > size / 2:
        raise ValueError("invalid thumbnail geometry")
    fill = tuple(matte if background is None else background)
    content = ImageOps.contain(image.convert("RGBA"), (size, size), Image.Resampling.LANCZOS)
    square = Image.new("RGB", (size, size), fill)
    square.paste(content, ((size - content.width) // 2, (size - content.height) // 2), content)
    if radius:
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=radius * 4, fill=255)
        mask = mask.resize((size, size), Image.Resampling.BOX)       # BOX: LANCZOS rings at the edge of the mask
        rounded = Image.new("RGB", (size, size), tuple(matte))
        rounded.paste(square, (0, 0), mask)
        return rounded
    return square


def colpic(path, size, matte=None, radius=0, background=None):
    """ColPic of a gcode thumbnail. New pages can request an exact size, matte and rounded corners."""
    from librescreen.screen import colpic as screen_colpic
    thumb = find(path, size, "PNG")
    if thumb is None:
        raise IOError("no thumbnail in %s" % path)
    image = _screen_image(thumb, False)
    image = _flatten(image) if matte is None else prepare_picture(image, size, matte, radius, background)
    return screen_colpic.encode_picture(image, size)


LIST_SIZE = 112          # the thumbnails of the slots of the file list (112 x 112 like the -112x112_QD.jpg of the original): a multiple of 16 (the MCU of a 4:2:0 JPEG)


def jpeg(path, size, matte=(41, 40, 41), radius=8, background=(49, 48, 57)):
    """A size x size baseline JPEG of the file's thumbnail for the screen's picture memory (turned like the ``-112x112_QD.jpg`` of the original);
    the card colour and the round corners are in the pixels (JPEG has no alpha); None if the file has no thumbnail."""
    thumb = choose_sharpest(get_thumbnails(path))
    if thumb is None:
        return None
    try:
        image = prepare_picture(_screen_image(thumb), size, matte, radius, background)
        out = io.BytesIO()
        # 4:4:4: the screen draws the colour of 4:2:0 in blocks of 2 x 2 pixels (the thin lines of a model get coloured edges); the size stays a multiple of 16
        # (LIST_SIZE), else the screen draws the rows sheared ("a staircase")
        image.save(out, "JPEG", quality=95, subsampling=0, progressive=False, optimize=False)
        return out.getvalue()
    except Exception as e:
        _log("%s: %s" % (path, e))
        return None
