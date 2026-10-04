#!/usr/bin/env python3
"""Contact sheets (12 pages each) of the pictures made by snap_pages.cs.

    python3 tools/emulator/snap_sheets.py SNAPS_DIR PAGES.txt OUT_DIR
"""
import os
import sys

from PIL import Image, ImageDraw


def main(snaps, pages, out):
    names = [line.strip() for line in open(pages) if line.strip()]
    os.makedirs(out, exist_ok=True)
    per = 12
    for start in range(0, len(names), per):
        sheet = Image.new("RGB", (6 * 180, 2 * 336), (60, 60, 60))
        draw = ImageDraw.Draw(sheet)
        for j, name in enumerate(names[start:start + per]):
            image = Image.open(os.path.join(snaps, name + ".png")).convert("RGB").resize((176, 320), Image.LANCZOS)
            x, y = (j % 6) * 180, (j // 6) * 336
            sheet.paste(image, (x + 2, y + 14))
            draw.text((x + 4, y + 2), name, fill=(255, 220, 120))
        sheet.save(os.path.join(out, "sheet_%d.png" % (start // per)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
