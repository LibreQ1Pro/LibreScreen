#!/usr/bin/env python3
"""Contact sheet of pictures by id (the position in project.json), to see what a picture id sent by the host shows.

    python3 display_firmware/tools/pic_sheet.py OUT.png 32 33 122-126 ...
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, PER = 136, 240, 8


def ids(args):
    out = []
    for a in args:
        lo, _, hi = a.partition("-")
        out += range(int(lo), int(hi or lo) + 1)
    return out


def main():
    pictures = [p["key"] for p in json.load(open(os.path.join(ROOT, "project.json")))["pictures"]]
    wanted = ids(sys.argv[2:])
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    rows = (len(wanted) + PER - 1) // PER
    sheet = Image.new("RGB", (PER * (W + 4), rows * (H + 22)), (255, 0, 255))
    for n, pid in enumerate(wanted):
        im = Image.open(os.path.join(ROOT, "pictures", pictures[pid] + ".png")).convert("RGBA")
        back = Image.new("RGBA", im.size, (255, 0, 255, 255))
        back.alpha_composite(im)
        x, y = (n % PER) * (W + 4), (n // PER) * (H + 22)
        sheet.paste(back.convert("RGB").resize((W, H)), (x, y + 20))
        ImageDraw.Draw(sheet).text((x + 2, y + 1), "%d %s" % (pid, pictures[pid][:14]), fill=(255, 255, 255), font=font)
    sheet.save(sys.argv[1])


if __name__ == "__main__":
    main()
