#!/usr/bin/env python3
"""The new project must do what the stock project did when a widget is touched.

    python3 tools/test_behaviour.py [--rev REV] [page ...]          (run from display_firmware/; needs hmi-builder and git)

The stock project (the git revision REV, default HEAD) and the current one are run in the emulator of hmi-builder; for every page, every
component that both have (by name, or by the new name of an alias of tools/page_rules.py) is touched in each, and the frames the screen sends to the host
(``65 page widget``, ``71 ...``) are compared. A component that the rules changed on purpose is listed in ``CHANGED`` (with why).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import tile_core as core

core.builder_path()
from hmi_emu.device import Device, END               # noqa: E402
from hmi_emu.project import Project                  # noqa: E402

ROOT = Path(core.ROOT)
import page_names                                    # noqa: E402
import page_rules                                    # noqa: E402

# (page, component): why the frames differ
CHANGED = {
    ("filament_kb", "key_ok"): "the value keyboard sends the number from the typed text, not from a widget of another page",
    ("keybdB", "key_ok"): "the value keyboard sends the number from the typed text, not from a widget of another page",
    ("filament", "fan1_btn"): "the fan tiles open the number keyboard",
    ("filamentVideo2", "next"): "the button waits for the temperature: the screen sends nothing until the host has told it the nozzle is hot (cur_val, tar_val)",
    ("filament", "bed_set"): "the stock page sent the frame twice (the row and the number both fired it); now once",
    ("filament", "bed_row"): "the stock page sent the frame twice; now once",
    ("filament", "chamber_set"): "the stock page sent the frame twice; now once",
    ("filament", "chamber_row"): "the stock page sent the frame twice; now once",
}


def export(rev, target):
    top = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], text=True).strip()
    prefix = str(ROOT.relative_to(top))
    archive = subprocess.Popen(["git", "-C", top, "archive", rev, prefix], stdout=subprocess.PIPE)
    subprocess.check_call(["tar", "-x", "-C", target], stdin=archive.stdout)
    archive.wait()
    return Path(target) / prefix


def normalised(data, keys):
    """The frames with the page number replaced by the name of the page (the ids of the pages differ between the two projects)."""
    out = []
    for frame in data.split(END):
        if frame[:1] in (b"\x65", b"\x71") and len(frame) > 1:
            frame = frame[:1] + page_names.stock(keys[frame[1]]).encode() + b":" + frame[2:]
        out.append(frame)
    return out


def frames_of(project, page, name, keys, logo="boot_logo"):
    sent = []
    dev = Device(project, sent.append, boot_frame=False)
    for line in ("lang=2", logo + ".version.val=100", "page " + page):
        dev.feed(line.encode("utf-8") + END)
    obj = next((o for o in dev.objects() if o.name == name), None)
    if obj is None or not obj.visible or "x" not in obj.attrs:
        return None
    sent.clear()
    x, y = obj.attrs["x"] + obj.attrs["w"] // 2, obj.attrs["y"] + obj.attrs["h"] // 2
    dev.tap(x, y)
    return normalised(b"".join(sent), keys)


def main():
    args = sys.argv[1:]
    rev = "HEAD"
    if "--rev" in args:
        i = args.index("--rev")
        rev = args[i + 1]
        del args[i:i + 2]
    with tempfile.TemporaryDirectory() as tmp:
        old_dir = export(rev, tmp)
        old, new = Project(str(old_dir)), Project(str(ROOT))
        old_keys = [p["key"] for p in json.loads((old_dir / "project.json").read_text())["pages"]]
        new_keys = [p["key"] for p in json.loads((ROOT / "project.json").read_text())["pages"]]
        pages = args or [p["key"] for p in json.loads((ROOT / "project.json").read_text())["pages"]]
        checked = problems = 0
        for page in pages:
            stock_page = page_names.stock(page)
            alias = page_rules.RULES.get(stock_page, {}).get("aliases", {})
            data = json.loads((ROOT / "pages" / (page + ".json")).read_text(encoding="utf-8"))
            for obj in data["objects"]:
                name = obj["attributes"]["objname"]
                if obj["type"] not in ("button", "touch_hotspot", "text", "number", "picture") or not (obj["events"].get("codesup") or obj["events"].get("codesdown")):
                    continue
                stock = alias.get(name, name)
                a, b = frames_of(old, stock_page, stock, old_keys, "logo"), frames_of(new, page, name, new_keys)
                if a is None or b is None:
                    continue
                checked += 1
                if a != b and (stock_page, name) not in CHANGED:
                    problems += 1
                    print("%s.%s: stock %s, now %s" % (page, name, a, b))
        print("%d components touched, %d differ" % (checked, problems))
        return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
