#!/usr/bin/env python3
"""Checks that the pictures of a page, drawn one over another, give the rendering of the mockup (the picture and button components, in the order of the page; texts and
what the host / screen fills in at run time are left out on both sides).

    python3 tools/check_composition.py [PAGE ...]      report the pages whose picture layer misses something of the mockup (exit code 1)

Why: the decor is made without the widgets that are components of their own (a card that is a button, an icon): a widget that has no tile of its own would vanish from the page.
"""
import json
import sys

from PIL import Image, ImageChops

import gen_project as gp
import page_names
from migrate_pages import spec_pages

LIMIT = 40          # pixels that differ by more than 24 / 255 outside the texts, per page


def rgb565(value):
    return (((value >> 11) & 31) * 255 // 31, ((value >> 5) & 63) * 255 // 63, (value & 31) * 255 // 31)


def compose(page):
    root = page["root"]["attributes"]
    canvas = Image.new("RGB", (272, 480), rgb565(root.get("bco", 0)))
    covered = []
    for obj in page["objects"]:
        a = obj["attributes"]
        if obj["type"] not in ("picture", "button"):
            continue
        ref = a.get("pic")
        if not isinstance(ref, dict) or not ref.get("$ref", "").startswith("picture:"):
            continue
        tile = Image.open(gp.ROOT / "pictures" / (ref["$ref"].split(":", 1)[1] + ".png")).convert("RGBA")
        canvas.paste(tile, (a["x"], a["y"]), tile)
    return canvas


def main():
    wanted = set(sys.argv[1:])
    bad = 0
    for old, specs in sorted(spec_pages().items()):
        base = specs[0]
        if wanted and base["page"] not in wanted and old not in wanted:
            continue
        path = page_names.page_file(old)
        try:
            page = json.load(open(path, encoding="utf-8"))
        except OSError:
            continue
        got = compose(page)
        want = gp.screenshot(base["id"], base["variant"], 2)
        diff = ImageChops.difference(got, want).convert("L").point(lambda v: 255 if v > 24 else 0)
        # only what the mockup shows and the pictures do not: a component that is hidden at first (a button that comes later) adds to the pictures, and that is fine
        ground = Image.new("RGB", (272, 480), rgb565(page["root"]["attributes"].get("bco", 0)))
        shown = ImageChops.difference(want, ground).convert("L").point(lambda v: 255 if v > 24 else 0)
        diff = ImageChops.multiply(diff, shown)
        # texts and values (hidden in the static rendering anyway) and the animations / thumbnails are components of other kinds
        for w in base["widgets"]:
            if w["kind"] in ("t", "thumb", "anim", "bar"):
                diff.paste(0, (w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"]))
        count = sum(1 for v in diff.get_flattened_data() if v) if hasattr(diff, 'get_flattened_data') else sum(1 for v in diff.getdata() if v)
        if count > LIMIT:
            bad += 1
            box = diff.getbbox()
            print("%-18s %5d pixels differ, within %s" % (base["page"], count, box))
    print("%d pages differ" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
