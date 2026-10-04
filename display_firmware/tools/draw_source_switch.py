#!/usr/bin/env python3
"""Redraws the switch of the network page (which interface the IP box shows) as a two-segment control: Wi-Fi | LAN.

    python3 tools/draw_source_switch.py        (run from display_firmware/; rewrites the region in four pictures)

The stock switch was a cable plug and a toggle, which does not say what the two positions are. Now the left segment is
the Wi-Fi icon and the right one the LAN (ethernet port) icon; the active one is blue. Icons: Lucide (ISC license),
icons/wifi.svg and icons/ethernet-port.svg, rendered with Inkscape.

``ip_switch_off`` / ``ip_press_off``  Wi-Fi is shown (``mks_ethernet`` = 0)
``ip_switch_on``  / ``ip_press_on``   LAN is shown (``mks_ethernet`` = 1)
``ip_switch_*`` are the normal look of the button (transparent around it), ``ip_press_*`` the pressed look inside the
picture of the whole page; only the rectangle of the button (18,114 88x40) is changed.
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
X, Y, W, H = 18, 114, 88, 40
SCALE = 4
RADIUS = 6
PANEL = (38, 38, 38)
NORMAL = (102, 102, 102)
PRESSED = (70, 70, 70)
BLUE = (68, 121, 251)
ICON_ACTIVE = (255, 255, 255)
ICON_IDLE = (178, 178, 178)
ICON = 22


def icon(name, colour, size):
    """The Lucide icon as an RGBA image of size x size pixels in the given colour."""
    svg = open(os.path.join(ROOT, "icons", name + ".svg"), encoding="utf-8").read()
    svg = svg.replace("currentColor", "#%02x%02x%02x" % colour)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "i.svg"), os.path.join(tmp, "i.png")
        open(src, "w", encoding="utf-8").write(svg)
        subprocess.run(["inkscape", src, "--export-type=png", "--export-filename=" + dst,
                        "--export-width=%d" % size, "--export-height=%d" % size], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Image.open(dst).convert("RGBA")


def rounded_mask(w, h, radius, corners=(True, True, True, True)):
    mask = Image.new("L", (w * SCALE, h * SCALE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * SCALE - 1, h * SCALE - 1), radius=radius * SCALE, fill=255,
                                           corners=corners)
    return mask.resize((w, h), Image.LANCZOS)


def control(lan, pressed):
    """The 88x40 control as RGBA with transparent corners; lan = the right segment is the active one."""
    base = PRESSED if pressed else NORMAL
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (W, H), base + (255,)), (0, 0), rounded_mask(W, H, RADIUS))
    inset = 4
    inner = (W - 2 * inset) // 2                    # both segments are the same size (40 x 32), the frame is 4 px
    seg = rounded_mask(inner, H - 2 * inset, RADIUS - 2)
    im.paste(Image.new("RGBA", seg.size, BLUE + (255,)), (inset + (inner if lan else 0), inset), seg)
    for index, name in enumerate(("wifi", "ethernet-port")):
        active = (index == 1) == lan
        glyph = icon(name, ICON_ACTIVE if active else ICON_IDLE, ICON * SCALE).resize((ICON, ICON), Image.LANCZOS)
        # the drawn part of a Lucide icon is not centred in its 24 x 24 box (the Wi-Fi fan sits low): centre what is drawn
        left, top, right, bottom = glyph.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        cx = inset + inner * index + inner / 2
        cy = H / 2
        im.alpha_composite(glyph, (round(cx - (left + right) / 2), round(cy - (top + bottom) / 2)))
    return im


def put(name, lan, pressed, transparent):
    path = os.path.join(ROOT, "pictures", name + ".png")
    pic = Image.open(path).convert("RGBA")
    ctl = control(lan, pressed)
    region = Image.new("RGBA", (W, H), (0, 0, 0, 0) if transparent else PANEL + (255,))
    region.alpha_composite(ctl)
    pic.paste(region, (X, Y))
    pic.convert("RGBA" if transparent else "RGB").save(path)


def main():
    put("ip_switch_off", False, False, True)
    put("ip_switch_on", True, False, True)
    put("ip_press_off", False, True, False)
    put("ip_press_on", True, True, False)


if __name__ == "__main__":
    main()
