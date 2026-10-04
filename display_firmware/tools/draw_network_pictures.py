#!/usr/bin/env python3
"""Draws the backgrounds of the network pages (net_bg_*.png) on top of pictures of the stock project.

    python3 tools/draw_network_pictures.py        (run from display_firmware/; overwrites pictures/net_bg_*.png)

Shapes are drawn 4 times larger and scaled down, so the corners are smooth (Pillow's own rounded_rectangle is not
antialiased and a radius of 6 comes out as an octagon). The base pictures are looked up by their stock names
(``pic_25`` is the panel with the header and the navigation bar, ``pic_313`` the stock network page) through
tools/names.json, so the script works before and after the renaming.
"""
import json
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALE = 4
RADIUS = 6

PANEL = (38, 38, 38)
BAR = (102, 102, 102)
BAR_PRESSED = (136, 136, 136)
RED = (150, 56, 56)
RED_PRESSED = (190, 84, 84)
BOX = (112, 112, 112)


def stock_picture(key):
    """The stock picture ``key`` (e.g. "pic_25") as an RGB image, whatever it is called now."""
    renamed = {}
    path = os.path.join(ROOT, "tools", "names.json")
    if os.path.exists(path):
        renamed = json.load(open(path, encoding="utf-8")).get("pictures", {})
    return Image.open(os.path.join(ROOT, "pictures", renamed.get(key, key) + ".png")).convert("RGB")


def rounded(img, rect, fill, radius=RADIUS):
    """Fills the rectangle (x0, y0, x1, y1; both ends included) with rounded, antialiased corners."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0 + 1, y1 - y0 + 1
    mask = Image.new("L", (w * SCALE, h * SCALE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * SCALE - 1, h * SCALE - 1), radius=radius * SCALE, fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    img.paste(Image.new("RGB", (w, h), fill), (x0, y0), mask)


def box(img, rect, width=2):
    """An outlined box: the border colour, then the panel colour inside."""
    x0, y0, x1, y1 = rect
    rounded(img, rect, BOX)
    rounded(img, (x0 + width, y0 + width, x1 - width, y1 - width), PANEL, RADIUS - width + 1)


def blank(base):
    im = base.copy()
    ImageDraw.Draw(im).rectangle((12, 58, 260, 112), fill=PANEL)       # the IP box and the refresh button
    return im


def draw_all():
    base = stock_picture("pic_25")
    pics = {"net_bg_blank": blank(base)}

    def pair(key, painter):
        for suffix, bar_c, red_c in (("", BAR, RED), ("_p", BAR_PRESSED, RED_PRESSED)):
            im = blank(base)
            painter(im, bar_c, red_c)
            pics[key + suffix] = im

    # wifi_list: the IP box became two buttons next to the refresh button
    for suffix, color in (("", BAR), ("_p", BAR_PRESSED)):
        im = base.copy()
        ImageDraw.Draw(im).rectangle((12, 58, 206, 112), fill=PANEL)
        rounded(im, (18, 64, 108, 104), color)
        rounded(im, (114, 64, 204, 104), color)
        pics["net_bg_list" + suffix] = im

    def detail(im, bar_c, red_c):
        box(im, (18, 64, 254, 144))
        for y in (164, 214, 264):
            rounded(im, (18, y, 254, y + 40), bar_c)
        rounded(im, (18, 314, 254, 354), red_c)

    def confirm(im, bar_c, red_c):
        box(im, (18, 70, 254, 250))
        rounded(im, (18, 280, 130, 328), red_c)
        rounded(im, (142, 280, 254, 328), bar_c)

    def info(im, bar_c, red_c):
        box(im, (18, 64, 254, 204))
        box(im, (18, 214, 254, 354))
        rounded(im, (18, 364, 254, 404), bar_c)

    pair("net_bg_detail", detail)
    pair("net_bg_confirm", confirm)
    pair("net_bg_info", info)

    # the network page: no bar for the QIDI "device code" any more
    im = stock_picture("pic_313")
    ImageDraw.Draw(im).rectangle((14, 360, 258, 408), fill=PANEL)
    pics["net_bg_internet"] = im
    return pics


if __name__ == "__main__":
    for key, image in draw_all().items():
        image.save(os.path.join(ROOT, "pictures", key + ".png"))
        print(key)
