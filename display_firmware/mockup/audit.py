#!/usr/bin/env python3
"""Checks the mockup in headless Chrome and prints what the screen could not show:

    python3 audit.py            hardware audit (index.html?audit=hw) + the spacing report (index.html?audit=1)
    python3 audit.py --hw       only the hardware audit
    python3 audit.py --json     the hardware audit as JSON
    python3 audit.py --names    writes names_map.json: per stock page, its new name and the widgets (same as the project / new in the mockup / gone)

The hardware audit draws every screen (every variant) in the 13 languages and checks: the six fonts (nothing else), text that does not
fit its widget, buttons whose content overflows, widgets outside the screen, touch regions smaller than 40, the coverage of the pages of
../project.json (a page without a screen, a screen of a page that does not exist, two base screens for one page), that a value never
moves or overflows its slot (the recipes of src/kit.js with the extreme examples of src/captions.js) and that the names the host cuts
to a slot stay within it. Exit status 1 when something fails; widget names longer than 14 characters (the limit of the editor) are only listed.
"""
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def dump(query, budget=120000):
    url = "file://%s/index.html?%s" % (HERE, query)
    out = subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=%d" % budget,
                          "--dump-dom", url], capture_output=True, text=True, timeout=600).stdout
    return out


def result(dom, ident):
    m = re.search(r'<pre id="%s">(.*?)</pre>' % ident, dom, re.S)
    if not m:
        sys.exit("the audit did not produce a result (is google-chrome installed and index.html built?)")
    return json.loads(html.unescape(m.group(1)))


def hardware(as_json):
    r = result(dump("audit=hw"), "hwaudit")
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 1 if (r["problems"] or r["stress"] or r["coverage"]["missing"] or r["coverage"]["unknown"] or r["coverage"]["duplicate"] or r["coverage"]["drawnRetired"]) else 0
    cov = r["coverage"]
    print("%d renders (every screen, every variant, 13 languages); fonts allowed: %s" % (r["renders"], ", ".join(sorted(r["fonts"]))))
    print("pages of the project: %d; without a screen: %s; screens of unknown pages: %s; pages drawn twice: %s" % (
        cov["pages"], cov["missing"] or "none", cov["unknown"] or "none", cov["duplicate"] or "none"))
    for line in cov.get("retired", []):
        print("  retired (no screen): " + line)
    if cov.get("drawnRetired"):
        print("  a retired page still has a screen: %s" % cov["drawnRetired"])
    for p in sorted(r["problems"], key=lambda p: (p["kind"], p["screen"], p["widget"])):
        print("  %-16s %-18s %-12s %-22s %s  [%s]" % (p["kind"], p["screen"], p["variant"], p["widget"], p["detail"], p["langs"]))
    for s in r["stress"]:
        print("  stress: %s" % json.dumps(s, ensure_ascii=False))
    if r["longNames"]:
        print("names longer than 14 characters (the limit of the editor; use a short name in the project): %d" % len(r["longNames"]))
        for n in r["longNames"]:
            print("    " + n)
    bad = len(r["problems"]) + len(r["stress"]) + len(cov["missing"]) + len(cov["unknown"]) + len(cov["duplicate"]) + len(cov.get("drawnRetired", []))
    print("FAIL: %d problems" % bad if bad else "OK: nothing the screen could not show")
    return 1 if bad else 0


def names():
    used = result(dump("audit=names", 60000), "names")
    pages = json.load(open(os.path.join(HERE, "pages.json"), encoding="utf-8"))["pages"]
    out = {}
    for old, new in sorted(pages.items()):
        path = os.path.join(HERE, "..", "pages", old + ".json")
        stock = [o["attributes"]["objname"] for o in json.load(open(path, encoding="utf-8"))["objects"]] if os.path.exists(path) else []
        mock = used.get(old, {}).get("widgets", [])
        out[old] = {"page": new, "screen": used.get(old, {}).get("id"),
                    "same": [w for w in stock if w in mock], "new": [w for w in mock if w not in stock], "gone": [w for w in stock if w not in mock]}
    json.dump(out, open(os.path.join(HERE, "names_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("names_map.json: %d pages, %d widgets kept, %d new, %d gone" % (len(out), sum(len(v["same"]) for v in out.values()),
          sum(len(v["new"]) for v in out.values()), sum(len(v["gone"]) for v in out.values())))


def spacing():
    r = result(dump("audit=1", 60000), "audit")
    odd = [(s["id"], {k: v for k, v in s["gaps"].items() if k[1:] != "8"}, s["margins"]) for s in r]
    print("\nspacing (informational: gaps other than 8, margins other than 12; headers, in-card items and slider internals are expected):")
    for sid, gaps, margins in odd:
        if gaps or margins:
            print("  %-16s gaps %s margins %s" % (sid, gaps, [m["n"] + ":" + str(m["l"]) + "/" + str(m["r"]) for m in margins]))


if __name__ == "__main__":
    if "--names" in sys.argv:
        names()
        sys.exit(0)
    status = hardware("--json" in sys.argv)
    if "--hw" not in sys.argv and "--json" not in sys.argv:
        spacing()
    sys.exit(status)
