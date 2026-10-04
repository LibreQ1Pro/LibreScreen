#!/usr/bin/env python3
"""Checks tools/faces.json (the looks the host gives its widgets with ``g.port.face(widget, state)``).

Every tile has to exist, every widget has to be a button / text / picture of some page whose size is the size of the tile,
and librescreen/screen/faces.py has to be what gen_faces.py writes from the file and the position of the pictures.
Run from display_firmware/:  python3 tools/lint_faces.py
"""
import glob
import json
import os
import struct
import sys

import gen_faces

ROOT = gen_faces.ROOT


def png_size(key):
    with open(os.path.join(ROOT, "pictures", key + ".png"), "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def main():
    problems = []
    with open(os.path.join(ROOT, "tools", "faces.json"), encoding="utf-8") as f:
        faces = json.load(f)
    sizes = {}
    for path in glob.glob(os.path.join(ROOT, "pages", "*.json")):
        with open(path, encoding="utf-8") as f:
            for obj in json.load(f)["objects"]:
                if obj["type"] in ("button", "text", "picture"):
                    a = obj["attributes"]
                    sizes.setdefault(obj["key"], set()).add((a["w"], a["h"]))
    with open(os.path.join(ROOT, "project.json"), encoding="utf-8") as f:
        keys = {p["key"] for p in json.load(f)["pictures"]}
    for widget, states in faces.items():
        if widget not in sizes:
            problems.append("%s: no such widget" % widget)
            continue
        for state, tiles in states.items():
            for tile in tiles:
                if tile is None:
                    continue
                if tile not in keys:
                    problems.append("%s/%s: no picture %s" % (widget, state, tile))
                elif png_size(tile) not in sizes[widget]:
                    problems.append("%s/%s: %s is %dx%d, the widget is %s" % (
                        widget, state, tile, *png_size(tile), sorted(sizes[widget])))
    with open(gen_faces.FACES_PY, encoding="utf-8") as f:
        if gen_faces.render() != f.read():
            problems.append("librescreen/screen/faces.py is out of date: run tools/gen_faces.py")
    for problem in sorted(set(problems)):
        print(problem)
    print("%d problems" % len(set(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
