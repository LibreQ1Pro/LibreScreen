#!/usr/bin/env python3
"""Makes the animations and the line art of the calibration pages from the hand-finished pictures (4 times the size):

    python3 tools/make_animations.py ~/Desktop/upscaled            (run from display_firmware/)

    video_*/NNN.png        the frames of the animations of the setup guide and the filament wizards
                           -> animations/<key>/NNN.png at the size of their block (248 x 192 for the setup guide, the wizards 212 x 150): scaled down with LANCZOS, a frame with
                              a transparent ground is put on the colour of the animation block (``.anim`` of the mockup), the corners are rounded (radius 12)
                              and painted with the colour of the page: the frames are opaque, the screen has no alpha for them
    bg_pre_bed_cal.png     -> mockup/art/pre_bed_cal.png            (248 x 80, transparent: the card of the page gives the ground)
    bg_bed_calibrate_*.png -> mockup/art/bed_calibrate_up/down.png  (120 x 140, transparent)
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "mockup" / "src" / "style.css").read_text(encoding="utf-8")
RADIUS = 12


def colour(rule):
    m = re.search(re.escape(rule) + r"\s*[:{][^;}]*?#([0-9a-fA-F]{6})", CSS)
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))


PAGE = colour("--bg")
BLOCK = tuple(int(v, 16) for v in re.findall(r"[0-9a-f]{2}", re.search(r"\.anim\{background:#([0-9a-f]{6})", CSS).group(1)))


def scaled(path, size):
    """Scaled to cover ``size`` and cropped in the middle (the aspect of 248 x 192 is 0.8 % off the one of the pictures)."""
    image = Image.open(path).convert("RGBA")
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left, top = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1]))


def rounded(frame, size):
    """The frame on the block colour (where it is transparent), its corners painted with the page colour."""
    ground = Image.new("RGBA", size, BLOCK + (255,))
    ground.alpha_composite(frame)
    image = ground.convert("RGB")
    scale = 8
    mask = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] * scale - 1, size[1] * scale - 1), radius=RADIUS * scale, fill=255)
    out = Image.new("RGB", size, PAGE)
    out.paste(image, (0, 0), mask.resize(size, Image.LANCZOS))
    return out


def centred(image, canvas):
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.paste(image, ((canvas[0] - image.width) // 2, (canvas[1] - image.height) // 2))
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    source = Path(sys.argv[1]).expanduser()
    for folder in sorted(source.glob("video_*")):
        key = folder.name
        existing = ROOT / "animations" / key
        frames = sorted(folder.glob("*.png"))
        size = Image.open(sorted(existing.glob("*.png"))[0]).size
        if size == (256, 200):
            size = (248, 192)            # the width of the content of a page (margin 12), a multiple of 8 high
        for frame in frames:
            rounded(scaled(frame, size), size).save(existing / frame.name)
        print("%-20s %d frames %dx%d" % (key, len(frames), size[0], size[1]))
    art = ROOT / "mockup" / "art"
    pre = scaled(source / "bg_pre_bed_cal.png", (232, 76))
    centred(pre, (248, 80)).save(art / "pre_bed_cal.png")
    for name in ("up", "down"):
        nut = scaled(source / ("bg_bed_calibrate_%s.png" % name), (112, 136))
        centred(nut, (120, 140)).save(art / ("bed_calibrate_%s.png" % name))
    print("art: pre_bed_cal, bed_calibrate_up, bed_calibrate_down")


if __name__ == "__main__":
    main()
