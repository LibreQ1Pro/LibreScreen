#!/usr/bin/env python3
"""The static layer of every screen of the mockup (cards, icons, buttons without their labels) cut into the pictures the screen project needs,
and what they cost in flash:

    python3 tools/slice_static.py [--out DIR]         (run from display_firmware/; needs google-chrome and the built mockup)

Every screen (and variant) is drawn in headless Chrome with the widgets of run time hidden (``index.html?bare=ID&static=1``), the page colour (#17171a)
is the background of the page (``sta=1``, ``bco``), the rest is cut into rectangles (the connected parts of what is not the page colour, close parts joined)
and every rectangle is one picture. Equal rectangles are one picture (the navigation bar, the back arrow ...). The size counts as the screen
stores a picture: 16 bit per pixel.
"""
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = os.path.join(ROOT, "mockup")
BG = (0x17, 0x17, 0x1a)
JOIN = 0


def shot(args):
    sid, variant, out = args
    q = "bare=%s&static=1" % sid + ("&variant=%s" % variant if variant else "")
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=272,480",
                    "--screenshot=" + out, "file://%s/index.html?%s" % (MOCK, q)], capture_output=True, timeout=120)
    return out


def rects(img):
    """Boxes of the parts that are not the page colour. Works on cells of 4 x 4 pixels (a part and its neighbour within JOIN pixels are one)."""
    a = np.asarray(img.convert("RGB")).astype(int)
    mask = np.abs(a - np.array(BG)).sum(axis=2) > 6
    c = 4
    h, w = mask.shape
    cells = mask.reshape(h // c, c, w // c, c).any(axis=(1, 3))
    grow = JOIN // c
    big = np.zeros_like(cells)
    for dy in range(-grow, grow + 1):
        for dx in range(-grow, grow + 1):
            sh = np.roll(np.roll(cells, dy, 0), dx, 1)
            big |= sh
    seen = np.zeros_like(big)
    boxes = []
    for y in range(big.shape[0]):
        for x in range(big.shape[1]):
            if big[y, x] and not seen[y, x]:
                stack, comp = [(y, x)], []
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    comp.append((cy, cx))
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < big.shape[0] and 0 <= nx < big.shape[1] and big[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                ys = [p[0] for p in comp]; xs = [p[1] for p in comp]
                sub = mask[min(ys) * c:(max(ys) + 1) * c, min(xs) * c:(max(xs) + 1) * c]
                yy, xx = np.where(sub)
                if len(yy):
                    boxes.append([min(xs) * c + int(xx.min()), min(ys) * c + int(yy.min()), min(xs) * c + int(xx.max()) + 1, min(ys) * c + int(yy.max()) + 1])
    return boxes


def main():
    out = os.path.join(ROOT, "out", "static")
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    os.makedirs(out, exist_ok=True)
    layout = json.load(open(os.path.join(MOCK, "layout.json"), encoding="utf-8"))
    jobs = [(s["id"], s["variant"], os.path.join(out, "%s%s.png" % (s["id"], "@" + s["variant"] if s["variant"] else ""))) for s in layout]
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        list(ex.map(shot, jobs))
    pics, per_page, raw = {}, {}, 0
    for sid, variant, path in jobs:
        img = Image.open(path).convert("RGB")
        r = rects(img)
        per_page[os.path.basename(path)] = r
        for x0, y0, x1, y1 in r:
            crop = img.crop((x0, y0, x1, y1))
            h = hashlib.sha1(crop.tobytes() + ("%d,%d" % (x1 - x0, y1 - y0)).encode()).hexdigest()[:10]
            pics.setdefault(h, (x1 - x0, y1 - y0, 0))
            w, hh, n = pics[h]
            pics[h] = (w, hh, n + 1)
            raw += (x1 - x0) * (y1 - y0) * 2
    unique = sum(w * h * 2 for w, h, n in pics.values())
    print("%d screens, %d rectangles, %d unique pictures; as drawn %.2f MB, unique %.2f MB (16 bit, no compression)" % (
        len(jobs), sum(len(v) for v in per_page.values()), len(pics), raw / 1e6, unique / 1e6))
    json.dump(per_page, open(os.path.join(out, "rects.json"), "w"))


if __name__ == "__main__":
    main()
