"""The engine of tile_pictures.py: cuts the look of a button out of the full-screen sheets of the stock project.

A stock button shows a part ("crop") of a full-screen picture, and the page background has the buttons drawn in; a
second sheet shows them pressed. Here a button is its own small picture (a tile): ``cut(project, page, rect, sheet)``
is what the stock project showed in the rectangle of the widget when the widget cropped ``sheet``: the page background
with the crop on top of it, with the pixels around the rounded corners made transparent.
"""
import hashlib
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # display_firmware/
SCREEN = (272, 480)


def builder_path():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_hmi
    path = os.path.join(build_hmi.find_builder(), "tools")
    if path not in sys.path:
        sys.path.insert(0, path)


def ref_key(value):
    """KEY of a {"$ref": "picture:KEY"} value, else None."""
    if isinstance(value, dict) and "$ref" in value:
        kind, _, key = value["$ref"].partition(":")
        return key if kind == "picture" else None
    return None


def ref(key):
    return {"$ref": "picture:%s" % key}


class Project(object):
    def __init__(self):
        builder_path()
        from hmi_emu.render import rgb565
        self.rgb565 = rgb565
        with open(os.path.join(ROOT, "project.json"), encoding="utf-8") as f:
            self.project = json.load(f)
        self.page_keys = [p["key"] for p in self.project["pages"]]
        self.pages = {}
        for key in self.page_keys:
            with open(os.path.join(ROOT, "pages", key + ".json"), encoding="utf-8") as f:
                self.pages[key] = json.load(f)
        self.sheets = {}
        self.backgrounds = {}

    def keys(self):
        return [p["key"] for p in self.project["pictures"]]

    def sheet(self, key):
        if key not in self.sheets:
            self.sheets[key] = Image.open(os.path.join(ROOT, "pictures", key + ".png")).convert("RGBA")
        return self.sheets[key]

    def background(self, page):
        """What the page shows behind its widgets (the renderer of the emulator draws it the same way)."""
        if page not in self.backgrounds:
            attrs = self.pages[page]["root"]["attributes"]
            img = Image.new("RGBA", SCREEN, (0, 0, 0, 255))
            if attrs.get("sta") == 1:
                img.paste(self.rgb565(attrs.get("bco", 0)), (0, 0) + SCREEN)
            elif attrs.get("sta") == 2 and ref_key(attrs.get("pic")):
                img.alpha_composite(self.sheet(ref_key(attrs["pic"])))
            self.backgrounds[page] = img
        return self.backgrounds[page]

    def widget(self, page, name):
        for obj in self.pages[page]["objects"]:
            if obj["key"] == name:
                return obj
        raise KeyError("%s has no widget %s" % (page, name))

    def save_page(self, page):
        with open(os.path.join(ROOT, "pages", page + ".json"), "w", encoding="utf-8") as f:
            json.dump(self.pages[page], f, ensure_ascii=False, indent=2)
            f.write("\n")


def rect_of(obj):
    a = obj["attributes"]
    return a["x"], a["y"], a["w"], a["h"]


def inside(rect):
    x, y, w, h = rect
    return x >= 0 and y >= 0 and x + w <= SCREEN[0] and y + h <= SCREEN[1] and w > 0 and h > 0


def clear_outside(tile, colours):
    """Makes every pixel that has one of the ``colours`` and is connected to the border of the tile transparent."""
    w, h = tile.size
    px = tile.load()
    stack = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
    stack += [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        if px[x, y][3] == 0 or px[x, y][:3] in colours:
            px[x, y] = (0, 0, 0, 0)
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return tile


def cut(project, page, rect, sheet):
    """The tile for ``rect`` of ``page`` when the widget crops ``sheet`` (None: nothing is cropped);
    returns (image, colour that was cleared or None, the image before the corners were cleared).

    A corner of the tile that has the colour of the background diagonally outside of it is not part of the button
    (a rounded corner): that colour is made transparent where it touches the border."""
    bg = project.background(page)
    x, y, w, h = rect
    tile = bg.crop((x, y, x + w, y + h))
    if sheet is not None:
        tile.alpha_composite(project.sheet(sheet).crop((x, y, x + w, y + h)))
    raw = tile.copy()
    found = []
    for (cx, cy), (ox, oy) in (((0, 0), (x - 1, y - 1)), ((w - 1, 0), (x + w, y - 1)),
                               ((0, h - 1), (x - 1, y + h)), ((w - 1, h - 1), (x + w, y + h))):
        if 0 <= ox < SCREEN[0] and 0 <= oy < SCREEN[1]:
            colour = tile.getpixel((cx, cy))[:3]
            if colour == bg.getpixel((ox, oy))[:3] and colour not in found:
                found.append(colour)
    if found:
        return clear_outside(tile, found), found[0], raw
    return tile, None, raw


def digest(image):
    return hashlib.md5(image.tobytes() + repr(image.size).encode()).hexdigest()


def is_blank(image):
    return image.getchannel("A").getextrema()[1] == 0
