#!/usr/bin/env python3
"""Rough preview of pages of the portable project: python3 tools/preview_page.py OUT.png page [page ...]
Background, cropped button pictures and text (Noto Sans stands in for the screen fonts, so widths are approximate)."""
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
SIZE = {"font_0": 18, "font_1": 24, "font_2": 14}


def color(v):
    return ((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)


def pic(key, cache={}):
    if key not in cache:
        cache[key] = Image.open(os.path.join(ROOT, "pictures", key + ".png")).convert("RGBA")
    return cache[key]


def key_of(v):
    return v["$ref"].split(":", 1)[1] if isinstance(v, dict) else None


SAMPLE = {      # what the host sends at run time
    "net_saved": {"row1_txt": "PonyTheBest-AsusWrt", "row2_txt": "OtterTeam-4G", "row3_txt": "MGTS_GPON_12F0", "row4_txt": "daisy"},
    "net_detail": {"ssid_txt": "PonyTheBest-AsusWrt", "status_txt": "Connected, 192.168.1.50", "connect_btn": "Disconnect",
                   "auto_btn": "Autoconnect: on"},
    "net_confirm": {"msg": "Forget\\r\"PonyTheBest-AsusWrt\"?\\rThe saved password\\rwill be deleted."},
    "net_info": {"wifi_txt": "Wi-Fi  wlx40a5ef2378f6\\rConnected\\rSSID  PonyTheBest-AsusWrt\\rIP  192.168.100.150\\rGW  192.168.100.1",
                 "lan_txt": "LAN  eth0\\rConnected\\rIP  192.168.199.104\\rGW  192.168.199.1\\rMAC  00:11:22:33:44:55",
                 "radio_btn": "Wi-Fi: on"},
    "wifi_list": {"row1_txt": "PonyTheBest-AsusWrt", "row2_txt": "OtterTeam-4G", "row3_txt": "PonyTheBest", "row4_txt": "MGTS_GPON_12F0",
                  "row5_txt": "Masha"},
}


def static_texts(d):
    """Texts set by codesload for the English / default branch (the block after ``}else``)."""
    lines, out, take = d["root"]["events"].get("codesload", []), {}, False
    for i, line in enumerate(lines):
        if line.strip() == "}else" and i + 1 < len(lines) and lines[i + 1].strip() == "{":
            take = True
        elif take and line.strip() == "}":
            take = False
        elif take:
            m = re.match(r'\s*(\w+)\.txt="(.*)"', line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def render(name):
    d = json.load(open(os.path.join(ROOT, "pages", name + ".json"), encoding="utf-8"))
    texts = dict(static_texts(d), **SAMPLE.get(name, {}))
    for o in d["objects"]:
        if o["key"] in texts:
            o["attributes"]["txt"] = texts[o["key"]]
    ra = d["root"]["attributes"]
    im = Image.new("RGBA", (272, 480), color(ra["bco"]))
    if ra.get("sta") == 2 and key_of(ra.get("pic")):
        im.alpha_composite(pic(key_of(ra["pic"])))
    dr = ImageDraw.Draw(im)
    for o in d["objects"]:
        a = o["attributes"]
        if o["type"] not in ("button", "text") or "x" not in a:
            continue
        x, y, w, h = a["x"], a["y"], a["w"], a["h"]
        if o["type"] == "button" and a.get("sta") == 0 and key_of(a.get("picc")):
            im.alpha_composite(pic(key_of(a["picc"])).crop((x, y, x + w, y + h)), (x, y))
        txt = a.get("txt", "")
        if not txt:
            continue
        font = ImageFont.truetype(FONT, SIZE.get(key_of(a.get("font")), 18))
        lines = txt.replace("\\r", "\n").replace("\r", "\n").split("\n")
        lh = font.size + 4
        top = y + (h - lh * len(lines)) // 2 if a.get("ycen", 1) == 1 else y
        for i, line in enumerate(lines):
            tw = dr.textlength(line, font=font)
            tx = x + (w - tw) / 2 if a.get("xcen", 1) == 1 else (x + w - tw if a.get("xcen") == 2 else x)
            dr.text((tx, top + i * lh), line, font=font, fill=color(a.get("pco", 65535)))
            if tw > w:
                dr.rectangle((x, y, x + w, y + h), outline=(255, 0, 0))     # text wider than the widget
    return im.convert("RGB")


if __name__ == "__main__":
    pages = sys.argv[2:]
    sheet = Image.new("RGB", (282 * len(pages), 480), (255, 0, 255))
    for i, n in enumerate(pages):
        sheet.paste(render(n), (i * 282, 0))
    sheet.save(sys.argv[1])
