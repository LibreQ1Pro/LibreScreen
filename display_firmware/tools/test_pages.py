#!/usr/bin/env python3
"""Loads every page of the project in the emulator of hmi-builder in each of the 13 languages and checks what the screen would show:

    python3 tools/test_pages.py [page ...]          (run from display_firmware/)

* the page loads without an error of the screen (a name that does not exist, an instruction that is not valid);
* every character of every text is in the font of the text (the glyph table), and the wrapped text of a widget is no taller than the widget;
* a text widget keeps within the screen;
* no line of a text starts or ends with a space (a centred line would be pushed to one side).
Exit status 1 when something fails.
"""
import json
import sys
from pathlib import Path

import tile_core as core

core.builder_path()
from hmi_emu.device import Device, END               # noqa: E402
from hmi_emu.project import Project                  # noqa: E402
from hmi_emu.render import Renderer                  # noqa: E402

ROOT = Path(core.ROOT)


def main():
    project = Project(str(ROOT))
    renderer = Renderer(project)
    pages = sys.argv[1:] or [p["key"] for p in json.loads((ROOT / "project.json").read_text())["pages"]]
    problems = []
    for page in pages:
        for lang in range(13):
            dev = Device(project, lambda data: None, boot_frame=False)
            for line in ("lang=%d" % lang, "boot_logo.version.val=101", "page " + page):
                dev.feed(line.encode("utf-8") + END)
                if dev.last_error:
                    problems.append("%s [%d]: %s: %s" % (page, lang, line, dev.last_error))
                    dev.last_error = None
            for obj in dev.objects()[1:]:
                a = obj.attrs
                if obj.type != "text" or not obj.visible or not a.get("txt") or "font" not in a:
                    continue
                font = renderer.font(a["font"])
                if font is None:
                    continue
                missing = [ch for ch in a["txt"] if ch not in "\r\n" and renderer._advance(a["font"], ch) is None]
                if missing:
                    problems.append("%s.%s [%d]: no glyph for %s" % (page, obj.name, lang, "".join(sorted(set(missing)))))
                if a["txt"] != a["txt"].strip(" ") or " \r" in a["txt"] or "\r " in a["txt"]:
                    problems.append("%s.%s [%d]: a space at the edge of a line pushes the centred text to one side: %r" % (page, obj.name, lang, a["txt"][:40]))
                lines = renderer._wrap(a["font"], a["txt"], a["w"], a.get("spax", 0), bool(a.get("isbr", 0)))
                if not a.get("isbr", 0):
                    for line in lines:
                        width = sum(renderer._advance(a["font"], ch) or 0 for ch in line)
                        if width > a["w"]:
                            problems.append("%s.%s [%d]: a line of %d px does not fit the %d px of the widget: %s" % (page, obj.name, lang, width, a["w"], line[:30]))
                height = len(lines) * (font.height + a.get("spay", 0)) - a.get("spay", 0)
                if height > a["h"]:
                    problems.append("%s.%s [%d]: %d lines need %d px, the widget has %d" % (page, obj.name, lang, len(lines), height, a["h"]))
                if a["x"] < 0 or a["y"] < 0 or a["x"] + a["w"] > 280 or a["y"] + a["h"] > 480:
                    if a["x"] < 272:           # the hidden variables of the preview page lie outside on purpose
                        problems.append("%s.%s: outside the screen" % (page, obj.name))
    for line in problems:
        print(line)
    print("%d problems in %d pages" % (len(problems), len(pages)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
