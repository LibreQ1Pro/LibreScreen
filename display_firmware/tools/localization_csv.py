#!/usr/bin/env python3
"""A CSV of the texts of the screen firmware, "before" and "after", every language in one row.

    python3 tools/localization_csv.py [OUT.csv] [GIT_REV]       (run from display_firmware/; default HEAD)

Columns: page, component, line, then a "before"/"after" pair per language (editor = the text the editor shows, zh ... he =
the ``lang==N`` branches of ``codesload``), changed. ``before`` is read from GIT_REV, ``after`` from the working tree.
``line`` numbers the texts of a component that gets several one after another (a keyboard title, a step label).
Line breaks of the screen (``\\r``) are written as spaces.
"""
import csv
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = ["zh", "ru", "en", "ja", "fr", "de", "it", "es", "ko", "pt", "ar", "tr", "he"]
COLS = ["editor"] + LANG
TXT = re.compile(r'^\s*([\w.]+)\.txt="(.*?)"(\s*//.*)?$')
HDR = re.compile(r"(?:\}\s*)?(?:else\s+)?if\(\s*lang\s*==\s*(\d+)\s*\)")


def clean(text):
    """One line: the screen's line breaks (a backslash and r in code, CR LF in an editor text) become spaces."""
    return re.sub(r"\s+", " ", text.replace("\\r", " ")).strip()


def safe(cell):
    """A text that starts with = + - @ would be taken for a formula by a spreadsheet: a space in front of it."""
    cell = str(cell)
    if cell[:1] in ("=", "+", "-", "@"):
        try:
            float(cell)
        except ValueError:
            return " " + cell
    return cell


def extract(page):
    out = {}
    for o in page["objects"]:
        if o["attributes"].get("txt"):
            out[(o["key"], 0, "editor")] = clean(o["attributes"]["txt"])
    lists = [page["root"]["events"].get("codesload", [])] + [o["events"][e] for o in page["objects"] for e in o["events"]]
    for n, lines in enumerate(lists):
        cur, count = None, {}
        for line in lines:
            s = line.strip()
            m = HDR.search(s)
            if m:
                cur = int(m.group(1))
                continue
            if s == "}else":
                cur = "else"
                continue
            m = TXT.match(line)
            if m and isinstance(cur, int) and cur < len(LANG):
                i = count[(m.group(1), cur)] = count.get((m.group(1), cur), 0) + 1
                out[(m.group(1), i + (100 if n else 0), LANG[cur])] = clean(m.group(2))
    return out


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), "localization_before_after.csv")
    rev = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    head = ["page", "component", "line"]
    for c in COLS:
        head += [c + " before", c + " after"]
    head.append("changed")
    rows = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "pages", "*.json"))):
        page = os.path.basename(path)[:-5]
        new = extract(json.load(open(path, encoding="utf-8")))
        try:
            old = extract(json.loads(subprocess.check_output(["git", "show", "%s:./pages/%s.json" % (rev, page)],
                                                             cwd=ROOT, stderr=subprocess.DEVNULL)))
        except subprocess.CalledProcessError:
            old = {}
        for comp, line in sorted({(k[0], k[1]) for k in set(old) | set(new)}):
            key = (page, comp, 1 if line == 0 else line % 100)
            row = rows.setdefault(key, [key[0], key[1], key[2]] + [""] * (2 * len(COLS)) + ["no"])
            for n, c in enumerate(COLS):
                k = (comp, 0, "editor") if c == "editor" else (comp, line, c)
                if (c == "editor") != (line == 0):
                    continue
                b, a = old.get(k, ""), new.get(k, "")
                row[3 + 2 * n], row[4 + 2 * n] = b, a
                if b != a:
                    row[-1] = "yes"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows([safe(c) for c in row] for row in rows.values())
    print("%d rows, %d changed -> %s" % (len(rows), sum(r[-1] == "yes" for r in rows.values()), out))


if __name__ == "__main__":
    main()
