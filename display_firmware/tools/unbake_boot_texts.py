#!/usr/bin/env python3
"""The texts of the pages ``shutdown``, ``restart`` and ``logo`` as text components, not as parts of pictures.

    python3 tools/unbake_boot_texts.py           (run from display_firmware/; safe to run again)

The stock pages were full-screen pictures with the English text drawn in. Now ``shutdown`` and ``restart`` have a plain
colour as their background (the pictures bg_shutdown / bg_restart are gone), ``logo`` keeps the picture of the logo
(now boot_logo, the text of its lower part is removed) and the texts are components in the 13 languages of the screen
(librescreen/util/netstrings.py: shutting_down, system_abnormal, restart_hint, booting_up).
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pictures import Pictures, ROOT                       # noqa: E402
from librescreen.util.netstrings import TEXT, LANGUAGES         # noqa: E402

BACKGROUND = 12710          # RGB565 of the (52, 52, 52) of the stock pictures
WHITE = 65535


def load(name):
    with open(os.path.join(ROOT, "pages", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def save(name, page):
    with open(os.path.join(ROOT, "pages", name + ".json"), "w", encoding="utf-8") as f:
        json.dump(page, f, ensure_ascii=False, indent=2)
        f.write("\n")


def label(template, name, key, x, y, w, h, xcen, ycen):
    obj = json.loads(json.dumps(template))
    obj["key"] = name
    obj["events"] = {k: [] for k in template["events"]}
    obj["attributes"].update({"objname": name, "x": x, "y": y, "w": w, "h": h, "xcen": xcen, "ycen": ycen,
                              "pco": WHITE, "isbr": 1, "txt_maxl": 150,
                              "txt": TEXT[key][LANGUAGES.index("en")]})
    return obj


def chain(texts):
    """codesload lines: {object: TEXT key} -> the usual if(lang==N) chain."""
    lines = []
    for n in range(len(LANGUAGES)):
        lines += ["%sif(lang==%d)" % ("}else " if n else "", n), "{"]
        lines += ['  %s.txt="%s"' % (obj, TEXT[key][n]) for obj, key in texts.items()]
    return lines + ["}"]


def plain_page(name, labels, pics):
    page = load(name)
    page["root"]["attributes"].pop("pic", None)
    page["root"]["attributes"].update({"sta": 1, "bco": BACKGROUND})
    if not page["objects"]:
        template = next(o for o in load("sleep_mode")["objects"] if o["key"] == "title")
        page["objects"] = [label(template, *args) for args in labels]
        page["root"]["events"]["codesload"] = chain({a[0]: a[1] for a in labels})
    save(name, page)


def main():
    pics = Pictures()
    if "bg_shutdown" in pics.keys():
        # (name, text key, x, y, w, h, xcen, ycen)
        plain_page("shutdown", [("msg", "shutting_down", 10, 185, 252, 110, 1, 1)], pics)
        plain_page("restart", [("title", "system_abnormal", 10, 90, 252, 115, 1, 1),
                               ("hint", "restart_hint", 20, 265, 232, 125, 0, 0)], pics)
        pics.remove(["bg_shutdown", "bg_restart"])

    page = load("logo")
    if not any(o["key"] == "boot_msg" for o in page["objects"]):
        path = os.path.join(ROOT, "pictures", ("boot_logo" if "boot_logo" in pics.keys() else "bg_logo") + ".png")
        img = Image.open(path).convert("RGBA")
        img.paste((52, 52, 52, 255), (0, 305, img.width, 395))       # "BOOTING UP, PLEASE WAIT......"
        img.save(path)
        template = next(o for o in load("sleep_mode")["objects"] if o["key"] == "title")
        page["objects"].append(label(template, "boot_msg", "booting_up", 21, 312, 230, 74, 0, 0))
        page["root"]["events"]["codesload"] += chain({"boot_msg": "booting_up"})
        save("logo", page)
    pics.save()
    print("done")


if __name__ == "__main__":
    main()
