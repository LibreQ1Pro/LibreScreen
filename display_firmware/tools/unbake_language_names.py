#!/usr/bin/env python3
"""The names of the languages on the language pages as text, not as parts of pictures.

    python3 tools/unbake_language_names.py          (run from display_firmware/; safe to run again)

The pages ``language``, ``language2`` and the same pages of the first start guide (``open_language``,
``open_language2``) show the buttons as crops of full-screen sheets with the name of the language drawn in (and a
sheet per state: normal, pressed, selected, selected + pressed). The names are removed from the sheets and every
button gets a text component with the name of its language in that language (it is not translated, the name is the
same in every language of the screen). The text of the selected language is white, the others grey, like the pictures
had it (the page code sets the colour). The sheets get names that tell their state and page.
"""
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pictures import Pictures, ROOT   # noqa: E402

NAMES = {"cn": "中文简体", "ru": "Русский", "en": "English", "jp": "日本語", "fr": "Français", "de": "Deutsch",
         "it": "Italiano", "es": "Español", "kr": "한국어", "pt": "Português", "ar": "العربية", "tr": "Türkçe",
         "he": "עברית"}
PAGES = ("language", "language2", "open_language", "open_language2")
GREY, WHITE = 48631, 65535          # RGB565 of (189, 189, 189) and white
TEXT_ROWS = (36, 62)                # rows of a 66 px high button that the text may touch (it is in rows 41..58)
TEXT_COLS = (14, 97)                # the columns of it (the corners of the button are outside)
CLEAN_ROW = 38                      # a row of the face between the ring and the text
RENAME = {
    "language_lang_cn": "language_btn", "language_lang_cn_press": "language_btn_press",
    "language_next_page_cn": "language_btn_selected", "hdr_back_press": "language_btn_selected_press",
    "language_prev_page": "language2_btn_selected", "language_prev_page_press": "language2_btn_press",
    "language2_lang_kr": "language2_btn", "language2_lang_kr_press_kr": "language2_btn_selected_press",
    "open_language_lang_cn": "open_language_btn", "open_language_lang_cn_press": "open_language_btn_press",
    "open_language_next_page_cn": "open_language_btn_selected",
    "open_language_next_press_cn": "open_language_btn_selected_press",
    "open_language_prev_page": "open_language2_btn_selected", "open_language_prev_page_press": "open_language2_btn_press",
    "open_language2_lang_kr": "open_language2_btn", "open_language2_lang_kr_press_kr": "open_language2_btn_selected_press",
}


def load(name):
    with open(os.path.join(ROOT, "pages", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def sheets_and_rects():
    """{sheet key: set of (x, y, w, h) of the language buttons that show a part of it}."""
    found = {}
    for name in PAGES:
        page = load(name)
        rects = {o["key"]: tuple(o["attributes"][k] for k in ("x", "y", "w", "h"))
                 for o in page["objects"] if o["key"].startswith("lang_")}
        for o in page["objects"]:
            if o["key"] in rects:
                for attr in ("picc", "picc2"):
                    ref = o["attributes"].get(attr)
                    if isinstance(ref, dict):
                        found.setdefault(ref["$ref"][8:], set()).add(rects[o["key"]])
        for line in page["root"]["events"]["codesload"]:
            m = re.match(r"\s*(lang_\w+)\.picc2?=\$\{picture:(\w+)\}", line)
            if m:
                found.setdefault(m.group(2), set()).add(rects[m.group(1)])
    return found


def erase(path, rects):
    img = Image.open(path).convert("RGBA")
    for x, y, w, h in rects:
        clean = img.crop((x + TEXT_COLS[0], y + CLEAN_ROW, x + TEXT_COLS[1], y + CLEAN_ROW + 1))
        for row in range(*TEXT_ROWS):
            img.paste(clean, (x + TEXT_COLS[0], y + row))
    img.save(path)


def main():
    pics = Pictures()
    for key, rects in sheets_and_rects().items():
        if key in pics.keys():                        # (not yet renamed: the names are removed once)
            erase(os.path.join(ROOT, "pictures", key + ".png"), rects)
    for old, new in RENAME.items():
        if old in pics.keys():
            pics.rename(old, new)

    template = next(o for o in load("sleep_mode")["objects"] if o["key"] == "title")
    for name in PAGES:
        page = load(name)
        keys = [o["key"] for o in page["objects"]]
        buttons = [o for o in page["objects"] if o["key"].startswith("lang_") and not o["key"].endswith("_name")]
        if any(k.endswith("_name") and k.startswith("lang_") for k in keys):
            continue
        for button in buttons:
            code = button["key"][5:]
            a = button["attributes"]
            label = json.loads(json.dumps(template))
            label["key"] = button["key"] + "_name"
            label["events"] = {k: [] for k in template["events"]}
            label["events"]["codesdown"] = ["click %s,1" % button["key"]]
            label["events"]["codesup"] = ["click %s,0" % button["key"]]
            label["attributes"].update({
                "objname": label["key"], "x": a["x"] + 6, "y": a["y"] + 36, "w": a["w"] - 12, "h": 26, "xcen": 1,
                "ycen": 1, "pco": GREY, "txt_maxl": 20, "isbr": 0, "txt": NAMES[code]})
            at = page["objects"].index(button) + 1
            page["objects"].insert(at, label)
        out = []
        for line in page["root"]["events"]["codesload"]:
            out.append(line)
            m = re.match(r"\s*(lang_\w+)\.picc=\$\{picture:\w+\}", line)
            if m:
                out.append("  %s_name.pco=%d" % (m.group(1), WHITE))
        page["root"]["events"]["codesload"] = out
        with open(os.path.join(ROOT, "pages", name + ".json"), "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False, indent=2)
            f.write("\n")
    pics.save()
    print("done")


if __name__ == "__main__":
    main()
