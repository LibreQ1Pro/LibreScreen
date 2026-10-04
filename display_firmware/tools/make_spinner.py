#!/usr/bin/env python3
"""The frames of the loading spinner (animations/spinner/NNN.png, 40 x 40) and its entry in project.json.

    python3 tools/make_spinner.py                  (run from display_firmware/)

A ring of the track colour with an arc of the accent colour that moves round it, twelve frames of 30 degrees; the frames are as opaque as the page
they lie on (the pages that wait have the plain page colour), so no alpha is needed. The mockup draws the same ring (``busy()`` in mockup/src/screens3.js).
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
KEY = "spinner"
SIZE, FRAMES, WIDTH = 40, 12, 3
BACKGROUND, TRACK, ACCENT = (24, 24, 24), (49, 48, 57), (57, 121, 255)
SS = 8


def ring_mask(big, inner, outer):
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((big / 2 - outer, big / 2 - outer, big / 2 + outer, big / 2 + outer), fill=255)
    draw.ellipse((big / 2 - inner, big / 2 - inner, big / 2 + inner, big / 2 + inner), fill=0)
    return mask


def frame(index):
    """The track is a ring, the accent is the same ring cut to a sector of 100 degrees with round ends (a mask, so no line is left where two shapes meet)."""
    big = SIZE * SS
    outer = big / 2
    inner = outer - WIDTH * SS
    ring = ring_mask(big, inner, outer)
    start = -90 + index * 360 // FRAMES
    sector = Image.new("L", (big, big), 0)
    ImageDraw.Draw(sector).pieslice((0, 0, big - 1, big - 1), start, start + 100, fill=255)
    arc = Image.new("L", (big, big), 0)
    arc.paste(ring, (0, 0), sector)
    middle = (outer + inner) / 2
    cap = WIDTH * SS / 2
    caps = ImageDraw.Draw(arc)
    for angle in (start, start + 100):
        x = big / 2 + middle * math.cos(math.radians(angle))
        y = big / 2 + middle * math.sin(math.radians(angle))
        caps.ellipse((x - cap, y - cap, x + cap, y + cap), fill=255)
    image = Image.new("RGB", (big, big), BACKGROUND)
    image.paste(Image.new("RGB", (big, big), TRACK), (0, 0), ring)
    image.paste(Image.new("RGB", (big, big), ACCENT), (0, 0), arc)
    return image.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    folder = ROOT / "animations" / KEY
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(FRAMES):
        frame(i).save(folder / ("%03d.png" % i))
    project = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
    entry = {"key": KEY, "fps": 10, "frames": [{"png": "animations/%s/%03d.png" % (KEY, i), "ms": 80} for i in range(FRAMES)]}
    project["animations"] = [e for e in project["animations"] if e["key"] != KEY] + [entry]
    (ROOT / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("%d frames of %s" % (FRAMES, KEY))


if __name__ == "__main__":
    main()
