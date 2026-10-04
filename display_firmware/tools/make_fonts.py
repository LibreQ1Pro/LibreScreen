#!/usr/bin/env python3
"""Render the six fonts of the new design (Pillow, fontTools and the installed Noto fonts).

    python3 tools/make_fonts.py [--check]

Text 13/400 and 19/600 contain the static translations; text 16/500 is the single wide font for host text.
It also covers the printable BMP characters of the old wide font for which Noto has a non-zero advance.
Digits 20/28/32 contain ASCII only, including '-'; units are separate text widgets. Text cells are
18/20/26 px; digit cells are ceil(size * 1.4 / 2) * 2. Glyphs are never silently clipped: a tall glyph is shifted
within the cell, or reduced if necessary. This is glyph rasterisation, NOT Arabic shaping or bidi layout.
--check renders and compares without writing. The host's width table comes from these same glyphs.
"""
import argparse
import math
import re
import os
import sys
import unicodedata
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

from build_hmi import find_builder

ROOT = Path(__file__).resolve().parent.parent
NOTO = Path("/usr/share/fonts/truetype/noto")
CJK = Path("/usr/share/fonts/opentype/noto")
BASE_K = 0.388
ROLES = {"t13": (13, "Regular"), "t16": (16, "Medium"), "t19": (19, "SemiBold"),
         "d20": (20, "SemiBold"), "d28": (28, "SemiBold"), "d32": (32, "SemiBold")}
DIGITS = " 0123456789.-/%+*:"
WIDTHS = ROOT.parent / "librescreen" / "screen" / "font_t16.widths"


def hmi_font():
    sys.path.insert(0, str(Path(find_builder()) / "tools"))
    import hmi_font
    return hmi_font


def event_lines(node):
    """Every line of event code of a page (a list of strings, anywhere in the page)."""
    if isinstance(node, list) and node and all(isinstance(x, str) for x in node):
        yield from node
    elif isinstance(node, dict):
        for value in node.values():
            yield from event_lines(value)
    elif isinstance(node, list):
        for value in node:
            yield from event_lines(value)


def charset():
    texts = json.loads((ROOT / "mockup/texts.json").read_text(encoding="utf-8"))
    chars = set(chr(c) for c in range(32, 127))
    chars.update("°℃…−↓中文简体РусскийEnglish日本語FrançaisDeutschItalianoEspañol한국어PortuguêsالعربيةTürkçeעברית")
    for page in texts.values():
        for entry in page.values():
            for value in (entry.values() if isinstance(entry, dict) else entry):
                if isinstance(value, str):
                    chars.update(value.replace("\n", "").replace("\r", ""))
    # the characters of the text the screen sets itself (``name.txt="..."`` in the event code of the pages: the keys of the keyboard ...)
    for path in list((ROOT / "pages").glob("*.json")) + list((ROOT / "tools" / "migration_sources").glob("*.json")):
        for line in event_lines(json.loads(path.read_text(encoding="utf-8"))):
            for found in re.findall(r'\.txt="((?:[^"\\]|\\.)*)"', line):
                chars.update(found.replace("\\\\", "\\").replace('\\"', '"').replace("\\r", ""))
    return chars


def source(ch, weight):
    """Preferred (path, face index); the wide-font builder checks the cmap before rendering."""
    o = ord(ch)
    cw = {"Regular": "Regular", "Medium": "Medium", "SemiBold": "Bold"}[weight]
    if 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
        return CJK / ("NotoSansCJK-%s.ttc" % cw), 1
    if 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF:
        return CJK / ("NotoSansCJK-%s.ttc" % cw), 0
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF or 0x2E80 <= o <= 0x2FDF:
        return CJK / ("NotoSansCJK-%s.ttc" % cw), 2
    if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return NOTO / ("NotoSansArabic-%s.ttf" % weight), 0
    if 0x0590 <= o <= 0x05FF or 0xFB1D <= o <= 0xFB4F:
        return NOTO / ("NotoSansHebrew-%s.ttf" % weight), 0
    if 0x2190 <= o <= 0x21FF:
        return NOTO / ("NotoSansSymbols-%s.ttf" % weight), 0
    return NOTO / ("NotoSans-%s.ttf" % weight), 0


class Faces:
    def __init__(self, size, weight):
        self.size, self.weight = size, weight
        self.fonts, self.cmaps = {}, {}

    def get(self, ch):
        cw = "Bold" if self.weight == "SemiBold" else self.weight
        candidates = [source(ch, self.weight), (CJK / ("NotoSansCJK-%s.ttc" % cw), 2),
                      (NOTO / "NotoSansSymbols2-Regular.ttf", 0)]
        for key in candidates:
            if key not in self.fonts:
                path, index = key
                with TTFont(path, fontNumber=index, lazy=True) as tt:
                    self.cmaps[key] = tt.getBestCmap() or {}
                self.fonts[key] = ImageFont.truetype(str(path), size=self.size, index=index,
                                                   layout_engine=ImageFont.Layout.BASIC)
            if ord(ch) in self.cmaps[key]:
                font = self.fonts[key]
                bbox = font.getbbox(ch, anchor="ls")
                if round(font.getlength(ch)) > 0 or bbox[2] > bbox[0]:
                    return font
        return None


def rasterize(ch, font, cell):
    """A glyph with a checked guard border, at the common baseline when its ink fits there."""
    baseline = round(cell / 2 + BASE_K * font.size)
    while True:
        bbox = font.getbbox(ch, anchor="ls")
        if bbox[3] - bbox[1] <= cell:
            break
        if font.size <= 1:
            raise ValueError("U+%04X cannot fit a %d-pixel cell" % (ord(ch), cell))
        font = font.font_variant(size=font.size - 1)
    baseline = max(-bbox[1], min(baseline, cell - bbox[3]))
    width = round(font.getlength(ch))
    left, right = max(0, -bbox[0]), max(0, bbox[2] - width)
    total = width + left + right
    margin = max(8, font.size * 2)
    canvas = Image.new("L", (total + 2 * margin, cell + 2 * margin), 0)
    ImageDraw.Draw(canvas).text((margin + left, margin + baseline), ch, font=font, fill=255, anchor="ls")
    ink = canvas.getbbox()
    if ink and (ink[0] < margin or ink[1] < margin or ink[2] > margin + total or ink[3] > margin + cell):
        raise ValueError("U+%04X would be clipped" % ord(ch))
    crop = canvas.crop((margin, margin, margin + total, margin + cell))
    values = crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata()
    alpha = [round(round(v * 7 / 255) * 255 / 7) for v in values]
    return {"width": width, "left": left, "right": right, "alpha": alpha}


def make(role, static, hf):
    size, weight = ROLES[role]
    digits = role.startswith("d")
    cell = {"t13": 18, "t16": 20, "t19": 26}.get(role, math.ceil(size * 1.4 / 2) * 2)
    wanted = set(DIGITS) if digits else set(static)
    if role == "t16":
        data = (ROOT / "fonts/font_title18.zi").read_bytes()
        wanted.update(chr(c) for c in hf._present_codes(data, hf.validate_font(data))
                      if chr(c).isprintable() and not unicodedata.combining(chr(c)))
    faces, glyphs, skipped = Faces(size, weight), {}, []
    for ch in sorted(wanted):
        font = faces.get(ch)
        if font is None:
            if ch in static or ch in DIGITS:
                raise ValueError("no font for required U+%04X" % ord(ch))
            skipped.append(ord(ch))
            continue
        glyphs[ord(ch)] = rasterize(ch, font, cell)
    if not digits:
        # The line break of a text is the control character CR (the "\\r" of the instructions). The device asks the font for its width when it measures a line
        # to centre it: a font without the glyph made every line that ends in a break look pushed to one side. The stock fonts have it (an empty glyph, 1 px).
        glyphs[0x0D] = {"width": 1, "left": 0, "right": 0, "alpha": [0] * cell}
    data = hf.encode_font(glyphs, cell, "librescreen_" + role, "ascii" if digits else "bmp", 3, _allow_controls=not digits)
    hf.validate_font(data)
    return data, glyphs, cell, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    static, hf = charset(), hmi_font()
    outputs = {}
    for role in ROLES:
        data, glyphs, cell, skipped = make(role, static, hf)
        outputs[ROOT / "fonts" / ("font_%s.zi" % role)] = data
        if role == "t16":
            widths = bytearray(65536)
            for code, glyph in glyphs.items():
                widths[code] = glyph["width"]
            outputs[WIDTHS] = bytes(widths)
        print("font_%s.zi: cell %d, %d glyphs, %d bytes, %d unsupported wide characters" %
              (role, cell, len(glyphs), len(data), len(skipped)), flush=True)
    # All fonts have to succeed before any resource is replaced.
    for path, data in outputs.items():
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                raise SystemExit("out of date: " + str(path))
        else:
            path.write_bytes(data)


if __name__ == "__main__":
    main()
