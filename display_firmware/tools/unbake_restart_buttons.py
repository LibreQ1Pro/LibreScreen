#!/usr/bin/env python3
"""The two restart buttons of the Klipper status page (``reset``) with their texts as text, not as picture.

    python3 tools/unbake_restart_buttons.py          (run from display_firmware/; safe to run again)

The buttons "RESTART KLIPPER" and "FIRMWARE RESTART" are crops of the sheets sys_ok_export_logs(_press), which had the
English text drawn in. The text is removed from the sheets (renamed klipper_status_buttons(_press): they hold the
faces of the buttons of the status pages) and the buttons get the text in the 13 languages of the screen
(librescreen/util/netstrings.py: restart_klipper, restart_firmware).
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pictures import Pictures, ROOT                       # noqa: E402
from librescreen.util.netstrings import TEXT, LANGUAGES         # noqa: E402

BUTTONS = (306, 356)            # y of the two buttons (x 15, 242 x 48)
X0, X1 = 15, 257
TEXT_ROWS = (16, 33)            # rows of a button that the text may touch (it is in rows 18..30)
CLEAN_ROW = 14                  # a row of the face without text
SHEETS = {"sys_ok_export_logs": "klipper_status_buttons", "sys_ok_export_logs_press": "klipper_status_buttons_press"}


def main():
    pics = Pictures()
    for old, new in SHEETS.items():
        if old in pics.keys():
            path = os.path.join(ROOT, "pictures", old + ".png")
            img = Image.open(path).convert("RGBA")
            for y in BUTTONS:
                clean = img.crop((X0, y + CLEAN_ROW, X1, y + CLEAN_ROW + 1))
                for row in range(*TEXT_ROWS):
                    img.paste(clean, (X0, y + row))
            img.save(path)
            pics.rename(old, new)

    path = os.path.join(ROOT, "pages", "reset.json")
    with open(path, encoding="utf-8") as f:
        page = json.load(f)
    comps = {o["key"]: o for o in page["objects"]}
    if "restart_klip" in comps and not comps["restart_klip"]["attributes"].get("txt"):
        model = comps["export_logs"]["attributes"]
        for name, key in (("restart_klip", "restart_klipper"), ("restart_fw", "restart_firmware")):
            a = comps[name]["attributes"]
            for k in ("font", "pco", "pco2", "xcen", "ycen", "txt_maxl", "isbr", "spax", "spay"):
                if k in model:
                    a[k] = model[k]
            a["txt"] = TEXT[key][LANGUAGES.index("en")]
        out = []
        for line in page["root"]["events"]["codesload"]:
            out.append(line)
            if line.strip().startswith("export_logs.txt="):
                n = len([l for l in out if l.strip().startswith("export_logs.txt=")]) - 1
                out.append('  restart_klip.txt="%s"' % TEXT["restart_klipper"][n])
                out.append('  restart_fw.txt="%s"' % TEXT["restart_firmware"][n])
        page["root"]["events"]["codesload"] = out
        with open(path, "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False, indent=2)
            f.write("\n")
    pics.save()
    print("done")


if __name__ == "__main__":
    main()
