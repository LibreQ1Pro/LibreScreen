#!/usr/bin/env python3
"""Checks that every frame the screen sends to the host ends with the terminator ``ff ff ff``.

    python3 tools/lint_frames.py          report (exit code 1 when something is wrong)
    python3 tools/lint_frames.py --fix    add the missing terminators in place

Why: ``prints`` / ``printh`` send the bytes as they are, without the end mark that the screen adds to the replies of
its own commands (``get``, ``sendme``). The host splits the byte stream into frames by the terminator, so a frame that
has none is glued to the next one and both are lost (see librescreen/screen/rx.py).

A frame is the run of ``prints`` / ``printh`` lines of an event; the logic between them (``output.val=...``) does not
end it. It is complete when the terminator (three ``prints 0xff,1`` lines, or ``printh ... ff ff ff``) follows, before
the end of the event or the closing brace of the branch.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINT = re.compile(r"\s*(prints|printh)\s+(.*)$")
FF = "prints 0xff,1"


def is_ff(line):
    return line.strip() == FF


def ends_with_ff(line):
    m = PRINT.match(line)
    return bool(m and m.group(1) == "printh" and m.group(2).lower().split()[-3:] == ["ff"] * 3)


def events(page):
    yield "root", page["root"]["events"]
    for o in page["objects"]:
        yield o["key"], o["events"]


def problems(lines):
    """Indexes of the lines after which a terminator is missing.

    A frame that was started inside a branch has to be closed before the branch ends; a frame started outside of
    it (a header printed before an ``if``) may be completed by the branches and closed after them."""
    out, last, born, ffs, depth = [], None, 0, 0, 0
    for i, line in enumerate(lines):
        s = line.strip()
        if is_ff(line):
            ffs += 1
            if ffs >= 3:
                last = None
            continue
        ffs = 0
        if PRINT.match(line):
            if last is None:
                born = depth
            last = None if ends_with_ff(line) else i
        elif s.startswith("}"):
            depth -= 1
            if last is not None and depth < born:
                out.append(last)
                last = None
        elif s == "{":
            depth += 1
    if last is not None:
        out.append(last)
    return out


def fix(lines):
    lines = list(lines)
    for i in reversed(problems(lines)):
        indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        m = PRINT.match(lines[i])
        if m.group(1) == "printh":
            lines[i] += " ff ff ff"
        else:
            lines[i + 1:i + 1] = [indent + FF] * 3
    return lines


def main():
    do_fix = "--fix" in sys.argv
    project = json.load(open(os.path.join(ROOT, "project.json"), encoding="utf-8"))
    bad = 0
    for p in project["pages"]:
        path = os.path.join(ROOT, p["content"]["path"])
        page = json.load(open(path, encoding="utf-8"))
        changed = False
        for key, evs in events(page):
            for name, lines in evs.items():
                if problems(lines):
                    bad += 1
                    print("%s: %s.%s" % (page["name"], key, name))
                    if do_fix:
                        evs[name] = fix(lines)
                        changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(page, f, ensure_ascii=False, indent=2)
                f.write("\n")
    print("%d events %s" % (bad, "fixed" if do_fix else "without the terminator"))
    return 0 if (do_fix or not bad) else 1


if __name__ == "__main__":
    sys.exit(main())
