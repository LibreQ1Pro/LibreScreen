#!/usr/bin/env python3
"""Writes layout.json: every screen and variant of the mockup as data (the named widgets with rectangle, kind, font role, colours).
It is the input of the generator of the screen project (../tools/gen_project.py):

    python3 export_layout.py
"""
import json
import os

import audit

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    data = audit.result(audit.dump("audit=layout", 60000), "layout")
    json.dump(data, open(os.path.join(HERE, "layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("layout.json: %d screens/variants, %d widgets" % (len(data), sum(len(s["widgets"]) for s in data)))


if __name__ == "__main__":
    main()
