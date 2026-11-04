#!/usr/bin/env python3
"""Checks the page ids that are written as numbers in the code of the pages.

The keyboards send ``prints 113,1`` (0x71, a value) followed by the id of the page the value belongs to; the host
dispatches on it (librescreen/screen/events.py). The id is the position of the page in project.json, so it has to change
whenever pages are added or removed before it.
The clicks written with a page number (``prints 0x65,1`` followed by a number instead of ``dp``) are checked too:
the sleep timer of the pages sends the id of the sleep page, the language pages send the id of the language
pages the host listens to.
Run from display_firmware/:  python3 tools/lint_page_ids.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED = {"keypad": "filament", "print_keypad": "printing"}


def blocks(o):
    if isinstance(o, list) and o and all(isinstance(x, str) for x in o):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from blocks(v)
    elif isinstance(o, list):
        for v in o:
            yield from blocks(v)


def main():
    project = json.load(open(os.path.join(ROOT, "project.json"), encoding="utf-8"))
    keys = [p["key"] for p in project["pages"]]
    problems = []
    for page, target in EXPECTED.items():
        want = keys.index(target)
        data = json.load(open(os.path.join(ROOT, "pages", page + ".json"), encoding="utf-8"))
        for lines in blocks(data):
            for i, line in enumerate(lines[:-1]):
                if line.strip() == "prints 113,1" and lines[i + 1].strip() != "prints %d,1" % want:
                    problems.append("%s: %s, the page '%s' is %d" % (page, lines[i + 1].strip(), target, want))
    allowed = {keys.index(k) for k in ("screen_asleep", "language", "setup_language")}
    for name in sorted(os.listdir(os.path.join(ROOT, "pages"))):
        data = json.load(open(os.path.join(ROOT, "pages", name), encoding="utf-8"))
        for lines in blocks(data):
            for i, line in enumerate(lines[:-1]):
                nxt = lines[i + 1].strip()
                if line.strip() == "prints 0x65,1" and nxt.startswith("prints ") and nxt != "prints dp,1":
                    number = nxt[len("prints "):].split(",")[0]
                    if not number.isdigit() or int(number) not in allowed:
                        problems.append("%s: click with the page %s, expected one of %s" % (name, number, sorted(allowed)))
    for p in sorted(set(problems)):
        print(p)
    print("%d problems" % len(set(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
