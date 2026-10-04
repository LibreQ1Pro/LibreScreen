#!/usr/bin/env python3
"""Renders the project before tile_pictures.py (a git revision) and the project as it is now with the emulator of
hmi-builder and compares the pictures in RGB565, the colours the screen has:

    python3 tools/tile_check.py REVISION        (run from display_firmware/; REVISION: the commit before the conversion)

1. every page, and every button of it pressed;
2. every look of tile_spec.py: the old widget gets ``.picc``/``.picc2`` of the stock sheets, the new one ``.pic``/``.pic2``
   of the tiles (tools/faces.json), released and pressed;
3. every button of every page touched once, twice and three times (the code of the pages changes looks on a touch:
   the language buttons, the shift key, the mute button ...).

Prints the differences and exits 1 when there are some. The debug pop-up of the main page (a wrong UI version) is hidden:
it is a translucent panel over other buttons, and its one-pixel border has a tint of what lies under it.
"""
import json
import os
import subprocess
import sys
import tempfile

import tile_core as core

core.builder_path()
from hmi_emu.device import Device, END               # noqa: E402
from hmi_emu.project import Project                  # noqa: E402
from hmi_emu.render import Renderer                  # noqa: E402
from tile_spec import SPEC                           # noqa: E402

ROOT = core.ROOT


def export(revision, target):
    top = subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--show-toplevel"], text=True).strip()
    prefix = os.path.relpath(ROOT, top)
    archive = subprocess.Popen(["git", "-C", top, "archive", revision, prefix], stdout=subprocess.PIPE)
    subprocess.check_call(["tar", "-x", "-C", target], stdin=archive.stdout)
    archive.wait()
    return os.path.join(target, prefix)


class Side(object):
    """One project in an emulated screen."""

    def __init__(self, directory):
        self.directory = directory
        self.project = Project(directory)
        self.device = Device(self.project, lambda data: None, boot_frame=False)
        self.renderer = Renderer(self.project)
        with open(os.path.join(directory, "project.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.pictures = [p["key"] for p in data["pictures"]]
        self.pages = [p["key"] for p in data["pages"]]

    def reset(self, page):
        self.device = Device(self.project, lambda data: None, boot_frame=False)
        self.show(page)

    def show(self, page):
        self.send("lang=2")
        self.send("page " + page)
        if page == "main":
            self.send("vis ver_warning,0")

    def send(self, text):
        self.device.feed(text.encode("utf-8") + END)

    def widgets(self):
        return [o for o in self.device.objects()[1:] if "x" in o.attrs]

    def press(self, name, pressed):
        for o in self.device.objects()[1:]:
            if o.name == name:
                o.pressed = pressed

    def picture(self):
        image = self.renderer.render(self.device).convert("RGB")
        return [(r >> 3, g >> 2, b >> 3) for r, g, b in image.get_flattened_data()] \
            if hasattr(image, "get_flattened_data") else [(r >> 3, g >> 2, b >> 3) for r, g, b in image.getdata()]


def differ(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(os.path.join(ROOT, "tools", "faces.json"), encoding="utf-8") as f:
        faces = json.load(f)
    problems = 0
    with tempfile.TemporaryDirectory() as tmp:
        old, new = Side(export(sys.argv[1], tmp)), Side(ROOT)
        checked = 0

        # 1. pages and pressed buttons
        for page in new.pages:
            old.reset(page)
            new.reset(page)
            names = [o.name for o in new.widgets() if o.type == "button" and o.visible]
            for pressed in [None] + names:
                for side in (old, new):
                    if pressed:
                        side.press(pressed, True)
                one, two = old.picture(), new.picture()
                for side in (old, new):
                    if pressed:
                        side.press(pressed, False)
                checked += 1
                if differ(one, two):
                    problems += 1
                    print("page %s%s differs in %d pixels" % (page, " (%s pressed)" % pressed if pressed else "", differ(one, two)))

        # 2. the looks
        for page, group, widgets, states in SPEC:
            for widget in widgets:
                for state, (released, pressed) in states.items():
                    images = []
                    for side in (old, new):
                        side.reset(page)
                        if side is old:
                            side.send("%s.picc=%d" % (widget, side.pictures.index(released)))
                            if pressed:
                                side.send("%s.picc2=%d" % (widget, side.pictures.index(pressed)))
                        else:
                            tiles = faces[widget][state]
                            side.send("%s.pic=%d" % (widget, side.pictures.index(tiles[0])))
                            if tiles[1]:
                                side.send("%s.pic2=%d" % (widget, side.pictures.index(tiles[1])))
                        shots = []
                        for hold in (False, True):
                            side.press(widget, hold)
                            shots.append(side.picture())
                            side.press(widget, False)
                        images.append(shots)
                    checked += 1
                    for hold in (0, 1):
                        if differ(images[0][hold], images[1][hold]):
                            problems += 1
                            print("look %s %s %s%s differs in %d pixels" % (
                                page, widget, state, " pressed" if hold else "", differ(images[0][hold], images[1][hold])))

        # 3. touches
        for page in new.pages:
            new.reset(page)
            targets = [o for o in new.widgets() if o.type in ("button", "text", "number") and o.visible and o.touch]
            for o in targets:
                x, y = o.attrs["x"] + o.attrs["w"] // 2, o.attrs["y"] + o.attrs["h"] // 2
                for times in (1, 2, 3):
                    images = []
                    for side in (old, new):
                        side.reset(page)
                        for _ in range(times):
                            side.device.touch(x, y, "down")
                            side.device.touch(x, y, "up")
                        if page == "main":
                            side.send("vis ver_warning,0")
                        images.append(side.picture())
                    checked += 1
                    if differ(*images):
                        problems += 1
                        print("page %s: touching %s %d times differs in %d pixels" % (page, o.name, times, differ(*images)))
    print("%d renderings compared, %d differ" % (checked, problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
