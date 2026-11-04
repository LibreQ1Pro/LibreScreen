#!/usr/bin/env python3
"""Adds the screen brightness setting to the screen sleep page and to the start-up program.

    python3 tools/add_brightness.py            apply (run from display_firmware/; safe to run again)

* ``Program.s`` reads ``max_dim`` (0..100, the brightness while the screen is awake; the pages already restore it with
  ``dim=max_dim``) from the EEPROM (address 300) and applies it;
* ``sleep_mode`` gets a label and a slider (10..100): moving the slider sets ``max_dim`` and ``dim`` at once, releasing
  it writes ``max_dim`` to the EEPROM (``wepo``);
* ``screen_sleep`` wakes up to ``max_dim`` instead of 100.
The label text of the 13 languages comes from librescreen/util/netstrings.py ("brightness").
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
from librescreen.util.netstrings import TEXT, LANGUAGES   # noqa: E402

LABEL = {"key": "brightness_lbl", "type": "text", "events": {}}
EEPROM_ADDRESS = 300


def load(name):
    with open(os.path.join(ROOT, "pages", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    with open(os.path.join(ROOT, "pages", name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sleep_mode():
    page = load("sleep_mode")
    title = next(o for o in page["objects"] if o["key"] == "title")
    fan = next(o for o in load("fila_set_fan")["objects"] if o["key"] == "fan1_slider")
    keys = [o["key"] for o in page["objects"]]

    if "brightness_lbl" not in keys:
        label = json.loads(json.dumps(title))
        label["key"] = "brightness_lbl"
        label["events"] = {k: [] for k in title["events"]}
        a = label["attributes"]
        a.update({"objname": "brightness_lbl", "x": 15, "y": 300, "w": 242, "h": 34, "xcen": 0, "ycen": 1,
                  "txt": TEXT["brightness"][LANGUAGES.index("en")]})
        slider = json.loads(json.dumps(fan))
        slider["key"] = "bright_slider"
        slider["events"] = {"codesdown": [], "codesup": ["wepo max_dim,%d" % EEPROM_ADDRESS],
                            "codesslide": ["max_dim=bright_slider.val", "dim=max_dim"]}
        s = slider["attributes"]
        s.update({"objname": "bright_slider", "x": 15, "y": 338, "w": 242, "h": 44, "sta": 1, "bco": 8452,
                  "bco1": 15327, "minval": 10, "maxval": 100, "val": 100})
        for k in ("picc", "picc1", "pic2"):          # solid colours: no pictures
            s[k] = 65535
        # before the navigation buttons, so that they stay on top
        at = keys.index("back_btn")
        page["objects"][at:at] = [label, slider]

    load_code = page["root"]["events"]["codesload"]
    if not any("brightness_lbl" in line for line in load_code):
        # one block per language: "if(lang==0)" / "}else if(lang==N)" up to the next one or the closing "}"
        head, blocks = [], []
        for line in load_code:
            if line.startswith(("if(lang==", "}else if(lang==")):
                blocks.append([line])
            elif not blocks:
                head.append(line)
            elif line != "}":
                blocks[-1].append(line)
        lines = list(head)
        for lang, block in enumerate(blocks):
            lines += block + ['  brightness_lbl.txt="%s"' % TEXT["brightness"][lang]]
        page["root"]["events"]["codesload"] = lines + ["}"]
    # the slider shows the stored value
    code = page["root"]["events"]["codesload"]
    if "bright_slider.val=max_dim" not in code:
        code.append("bright_slider.val=max_dim")
    save("sleep_mode", page)


def screen_sleep():
    page = load("screen_sleep")
    ev = page["root"]["events"]
    ev["codesunload"] = ["dim=max_dim" if l == "dim=100" else l for l in ev["codesunload"]]
    save("screen_sleep", page)


def program():
    path = os.path.join(ROOT, "Program.s")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "repo max_dim" in text:
        return
    anchor = "page ${page:logo}"
    block = ("repo max_dim,%d\nif(max_dim<10||max_dim>100)\n{\n  max_dim=100\n}\ndim=max_dim\n\n" % EEPROM_ADDRESS)
    text = text.replace(anchor, block + anchor, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    sleep_mode()
    screen_sleep()
    program()
    print("done")
