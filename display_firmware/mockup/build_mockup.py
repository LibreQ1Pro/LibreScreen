#!/usr/bin/env python3
"""Builds mockup/index.html (one file, nothing to install: open it in a browser) from mockup/src/*, mockup/texts.json
(tools/extract_texts.py), the Lucide icons of mockup/icons/ and the list of the pages of the screen project (../project.json, read as plain
JSON: the page names and their ids, so the audit can tell which page has no screen)."""
import glob
import json
import os
import sys
import re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import page_names as project_names      # noqa: E402


def read(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


def firmware_pages():
    """The pages of the screen project in the order of project.json (the index is the id the host sees)."""
    with open(os.path.join(HERE, "..", "project.json"), encoding="utf-8") as f:
        pages = json.load(f)["pages"]
    # the mockup is keyed by the stock names of the pages (the sources of the generator); the id is the position in the project
    return [{"id": i, "key": project_names.stock(p["key"])} for i, p in enumerate(pages)]


def page_names(pages):
    """pages.json: the old name of every page of the project -> its readable name (every page, no duplicates)."""
    names = json.loads(read("pages.json"))["pages"]
    keys = [p["key"] for p in pages]
    problems = ["no new name for %s" % k for k in keys if k not in names]
    problems += ["%s is not a page of the project" % k for k in names if k not in keys]
    problems += ["the name %s is used twice" % v for v in set(names.values()) if list(names.values()).count(v) > 1]
    if problems:
        raise SystemExit("pages.json: " + "; ".join(problems))
    return names


def main():
    texts = json.loads(read("texts.json"))
    icons = {}
    for path in glob.glob(os.path.join(HERE, "icons", "*.svg")):
        svg = open(path, encoding="utf-8").read()
        svg = re.sub(r'\s+(width|height)="24"', "", svg)
        svg = re.sub(r"\s+", " ", svg).strip()
        icons[os.path.basename(path)[:-4]] = svg
    parts = ["screens%d.js" % i for i in range(1, 10) if os.path.exists(os.path.join(HERE, "src", "screens%d.js" % i))]
    pages = firmware_pages()
    aliases = json.loads(read("pages.json")).get("gallery_aliases", {})
    js = "const TEXTS=%s;\nconst ICONS=%s;\nconst FW_PAGES=%s;\nconst PAGE_NAMES=%s;\nconst GALLERY_ALIASES=%s;\n" % (
        json.dumps(texts, ensure_ascii=False), json.dumps(icons), json.dumps(pages), json.dumps(page_names(pages)), json.dumps(aliases))
    js += read("src", "kit.js") + "\n" + read("src", "captions.js") + "\n" + "\n".join(read("src", p) for p in parts) + "\n" + read("src", "shell.js") + "\n" + read("export_spec.js") + "\ninit();\n"
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>QIDI Q1 Pro screen mockup</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>%s</style></head>
<body><div id="side"></div><div id="main"></div><div class="modal" id="modal"></div><script>%s</script></body></html>""" % (read("src", "style.css"), js)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html", len(html) // 1024, "KB")


if __name__ == "__main__":
    main()
