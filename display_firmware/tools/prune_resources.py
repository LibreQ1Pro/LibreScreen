#!/usr/bin/env python3
"""Removes what no page uses any more from the screen project: pictures, animations and fonts of the stock design.

    python3 tools/prune_resources.py [--dry-run]            (run from display_firmware/)

A picture is used when a page refers to it (``"$ref": "picture:KEY"`` or ``${picture:KEY}`` in event code), when Program.s does, or when the host
switches to it (a look of tools/faces.json); an animation by an ``animation`` component; a font by any component. The ids of the pictures are
positions, so librescreen/screen/faces.py is written again.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import gen_faces

ROOT = Path(__file__).resolve().parent.parent


def main():
    dry = "--dry-run" in sys.argv
    project = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
    text = "".join(path.read_text(encoding="utf-8") for path in (ROOT / "pages").glob("*.json")) + (ROOT / "Program.s").read_text(encoding="utf-8")
    faces = json.loads((ROOT / "tools" / "faces.json").read_text(encoding="utf-8"))
    face_tiles = {t for looks in faces.values() for pair in looks.values() for t in pair if t}
    used_pictures = set(re.findall(r"picture:([A-Za-z0-9_.\-]+)", text)) | face_tiles
    used_animations = set(re.findall(r"animation:([A-Za-z0-9_.\-]+)", text))
    used_fonts = set(re.findall(r"font:([A-Za-z0-9_.\-]+)", text))
    report = {}
    for kind, used in (("pictures", used_pictures), ("animations", used_animations), ("fonts", used_fonts)):
        drop = [e for e in project[kind] if e["key"] not in used]
        size = 0
        for e in drop:
            src = e.get("source", {})
            for rel in src.values():
                path = ROOT / rel
                if path.is_file():
                    size += path.stat().st_size
                    if not dry:
                        path.unlink()
            for frame in e.get("frames", []):
                path = ROOT / frame.get("png", "")
                if path.is_file():
                    size += path.stat().st_size
                    if not dry:
                        path.unlink()
            if not dry and kind == "animations":
                shutil.rmtree(ROOT / "animations" / e["key"], ignore_errors=True)
        report[kind] = (len(project[kind]), len(drop), size)
        if not dry:
            project[kind] = [e for e in project[kind] if e["key"] in used]
    for kind, (total, dropped, size) in report.items():
        print("%-10s %5d, %5d not used%s (%.1f MB of files)" % (kind, total, dropped, " (removed)" if not dry else "", size / 1e6))
    if not dry:
        (ROOT / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        gen_faces.main()


if __name__ == "__main__":
    main()
