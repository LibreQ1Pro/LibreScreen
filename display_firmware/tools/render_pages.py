#!/usr/bin/env python3
"""Draw actual .zi/picture resources beside the browser mockup, at 100% brightness.

    python3 tools/render_pages.py OUT.png PAGE [PAGE ...] [--lang N]

This runs only the display emulator, not librescreen. Each pair is emulator left / mockup right.
Browser intermediates stay in the firmware's ignored out/static directory.
"""
import argparse

from PIL import Image

import tile_core as core
from gen_project import load, screenshot

core.builder_path()
from hmi_emu.device import Device, END
from hmi_emu.project import Project
from hmi_emu.render import Renderer


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out")
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--lang", type=int, default=2)
    args = ap.parse_args()
    names = load("mockup/pages.json")["pages"]
    inverse = {v: k for k, v in names.items()}
    project, tiles = Project(core.ROOT), []
    renderer = Renderer(project)
    for name in args.pages:
        old = name if name in names else inverse[name]
        dev = Device(project, lambda data: None, boot_frame=False)
        for line in ("lang=%d" % args.lang, "boot_logo.version.val=100", "page " + old, "dim=100"):
            dev.feed(line.encode("utf-8") + END)
            if dev.last_error:
                raise RuntimeError("%s: %s" % (line, dev.last_error))
        variant = "no_values" if old == "main" else ""
        tiles.append((renderer.render(dev).convert("RGB"), screenshot(names[old], variant, args.lang, static=False)))
    sheet = Image.new("RGB", (len(tiles) * 560, 480), (60, 60, 60))
    for i, (actual, mockup) in enumerate(tiles):
        sheet.paste(actual, (i * 560, 0))
        sheet.paste(mockup, (i * 560 + 280, 0))
    sheet.save(args.out)


if __name__ == "__main__":
    main()
