#!/usr/bin/env python3
"""The fan sliders of the page ``fila_set_fan`` without the text baked into their pictures.

    python3 tools/unbake_fan_labels.py           (run from display_firmware/; safe to run again)

The stock page had 13 + 13 pictures (the track and the filled part of the sliders, one pair per language, with the names
of the three fans drawn in). Now there is one neutral track and one fill picture, and three text components with the
names in the 13 languages of the screen (the texts of the keyboard page, which names the same fans). The pointer
pictures of the sliders (a stray language list and the logo, never visible: the pointer size is 0) are gone.
"""
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pictures import Pictures, ROOT   # noqa: E402

BARS = (67, 183, 299)           # y of the three sliders
BAR_X, BAR_W, BAR_H = 26, 220, 42
TEXT_ROWS = (11, 32)            # rows of a bar that the text may touch (the text is in rows 13..28)
CLEAN_ROW = 6                   # a row of the bar without text: the bar is the same in every row there
LANGS = ("cn", "ru", "en", "jp", "fr", "de", "it", "es", "kr", "pt", "ar", "tr", "he")


def erase(src, dest):
    """Copies the picture without the text of the bars: the rows of the text get the pixels of a clean row."""
    img = Image.open(src).convert("RGBA")
    for y in BARS:
        clean = img.crop((BAR_X, y + CLEAN_ROW, BAR_X + BAR_W, y + CLEAN_ROW + 1))
        for row in range(*TEXT_ROWS):
            img.paste(clean, (BAR_X, y + row))
    img.save(dest)


def fan_titles(page_keyboard):
    """{fan index 0..2: [title per language]} from the keyboard page (titles 4, 5, 6 of its sys0 branches)."""
    sys0 = lang = None
    found = {}
    for line in page_keyboard["root"]["events"]["codesload"]:
        m = re.match(r"\s*(?:\}else )?if\(sys0==(\d+)\)", line)
        if m:
            sys0 = int(m.group(1))
        m = re.match(r"\s*(?:\}\s*else\s+)?if\(lang==(\d+)\)", line)
        if m:
            lang = int(m.group(1))
        m = re.match(r'\s*title\.txt="(.*)"$', line)
        if m and sys0 in (4, 5, 6):
            found.setdefault(sys0 - 4, {})[lang] = m.group(1)
    return {i: [found[i][n] for n in range(len(LANGS))] for i in range(3)}


def main():
    path = os.path.join(ROOT, "pages", "fila_set_fan.json")
    with open(path, encoding="utf-8") as f:
        page = json.load(f)
    pics = Pictures()
    if "fan_slider_track" not in pics.keys():
        erase(os.path.join(ROOT, "pictures", "fila_set_fan_fan1_slider_en.png"), "/tmp/fan_slider_track.png")
        erase(os.path.join(ROOT, "pictures", "fila_set_fan_fan1_slider_fg_en.png"), "/tmp/fan_slider_fill.png")
        old = [k for k in pics.keys() if k.startswith("fila_set_fan_fan1_slider_")] + ["fila_set_fan_fan2_slider_press"]
        at = pics.keys().index(old[0])
        pics.add("fan_slider_track", "/tmp/fan_slider_track.png", at)
        pics.add("fan_slider_fill", "/tmp/fan_slider_fill.png", at + 1)
    else:
        old = []

    for o in page["objects"]:
        if o["type"] == "slider":
            a = o["attributes"]
            a["picc"] = {"$ref": "picture:fan_slider_track"}
            a["picc1"] = {"$ref": "picture:fan_slider_fill"}
            a.update({"pic2": 65535, "psta": 0})
    keys = [o["key"] for o in page["objects"]]
    if "fan1_name" not in keys:
        with open(os.path.join(ROOT, "pages", "keybdB.json"), encoding="utf-8") as f:
            titles = fan_titles(json.load(f))
        template = next(o for o in load_page("sleep_mode")["objects"] if o["key"] == "title")
        labels = []
        for i, y in enumerate(BARS):
            label = json.loads(json.dumps(template))
            name = "fan%d_name" % (i + 1)
            label["key"] = name
            label["events"] = {k: [] for k in template["events"]}
            label["attributes"].update({"objname": name, "x": BAR_X + 4, "y": y, "w": BAR_W - 8, "h": BAR_H,
                                        "xcen": 1, "ycen": 1, "pco": 65535, "isbr": 0, "txt_maxl": 100,
                                        "txt": titles[i][LANGS.index("en")].replace("\\r", "\r\n")})
            labels.append(label)
        at = keys.index("fan1_val")
        page["objects"][at:at] = labels
        chain = []
        for n in range(len(LANGS)):
            chain += ["%sif(lang==%d)" % ("}else " if n else "", n), "{"]
            chain += ['  fan%d_name.txt="%s"' % (i + 1, titles[i][n]) for i in range(3)]
        page["root"]["events"]["codesload"] = chain + ["}"]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(page, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if old:
        pics.remove(old)
    pics.save()
    print("done")


def load_page(name):
    with open(os.path.join(ROOT, "pages", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
