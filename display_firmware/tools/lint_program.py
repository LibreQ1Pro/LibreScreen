#!/usr/bin/env python3
"""Checks Program.s against the pages: a global that no page or the host uses is reported, and so is a variable that a
page's code assigns or reads that is neither declared in Program.s nor a component / system variable.

    python3 tools/lint_program.py        (run from display_firmware/; exit 1 if there is a problem)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.path.join(os.path.dirname(ROOT), "librescreen")


def declared(text):
    names = []
    for line in text.splitlines():
        m = re.match(r"\s*int\s+(.*?)(//.*)?$", line)
        if m:
            names += [part.split("=")[0].strip() for part in m.group(1).split(",") if part.strip()]
    return names


def main():
    program = open(os.path.join(ROOT, "Program.s"), encoding="utf-8").read()
    names = declared(program)
    code = []
    for path in glob.glob(os.path.join(ROOT, "pages", "*.json")):
        page = json.load(open(path, encoding="utf-8"))
        events = [page["root"]["events"]] + [o["events"] for o in page["objects"]]
        code += [line for ev in events for lines in ev.values() for line in lines]
    code = "\n".join(code)
    host = "".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(HOST, "**", "*.py"), recursive=True))
    problems = []
    for name in names:
        if not re.search(r"\b%s\b" % name, code) and not re.search(r"\b%s\b" % name, host):
            problems.append("global %s is not used by any page or by the host" % name)
    for name in set(names):
        if names.count(name) > 1:
            problems.append("global %s is declared twice" % name)
    print("\n".join(problems) or "Program.s: %d globals, all used" % len(names))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
