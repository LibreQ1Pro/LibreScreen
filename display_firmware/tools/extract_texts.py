#!/usr/bin/env python3
"""Collects the texts of every page of the screen project in the 13 languages: mockup/texts.json
{page: {widget: [13 texts]}} (the English text of the component where the page has no chain for it)."""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = 13
IF = re.compile(r"^\s*(?:\}\s*else\s*)?if\(lang==(\d+)\)\s*$")
CTX = re.compile(r"^\s*(?:\}\s*else\s*)?if\((sys\d)==(\d+)\)\s*$")
SET = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\.txt="(.*)"\s*$')


def blocks(node):
    if isinstance(node, list) and node and all(isinstance(x, str) for x in node):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from blocks(v)
    elif isinstance(node, list):
        for v in node:
            yield from blocks(v)


def main():
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "pages", "*.json"))):
        page = os.path.basename(path)[:-5]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        texts = {}
        for o in data["objects"]:
            t = o["attributes"].get("txt")
            if t:
                texts[o["key"]] = [t] * LANGS
        for lines in blocks(data):
            lang = None
            ctx = ""
            for line in lines:
                m = CTX.match(line)
                if m:
                    ctx = "@%s=%s" % m.groups()
                    continue
                m = IF.match(line)
                if m:
                    lang = int(m.group(1))
                    continue
                m = SET.match(line)
                if m and lang is not None:
                    widget, text = m.groups()
                    if ctx:
                        texts.setdefault(widget + ctx, [""] * LANGS)[lang] = text.replace("\\r", "\n")
                        if widget in texts and texts[widget][0] == texts[widget][1] == texts[widget][2]:
                            pass
                        continue
                    texts.setdefault(widget, [""] * LANGS)
                    if texts[widget] == [texts[widget][0]] * LANGS and widget in {o["key"] for o in data["objects"]} \
                            and all(x == texts[widget][0] for x in texts[widget]):
                        pass
                    texts[widget][lang] = text.replace("\\r", "\n")
        out[page] = {k: v for k, v in texts.items()}
    # the texts the host sends itself (librescreen/util/netstrings.py)
    import sys
    sys.path.insert(0, os.path.dirname(ROOT))
    from librescreen.util.netstrings import TEXT
    out["net"] = {k: list(v) for k, v in TEXT.items()}
    os.makedirs(os.path.join(ROOT, "mockup"), exist_ok=True)
    with open(os.path.join(ROOT, "mockup", "texts.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(len(out), "pages")


if __name__ == "__main__":
    main()
