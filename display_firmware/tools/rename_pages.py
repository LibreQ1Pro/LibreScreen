#!/usr/bin/env python3
"""Gives the pages of the project their readable names and puts them in the order of the flow (``mockup/pages.json``: ``pages`` and ``order``):

    python3 tools/rename_pages.py            (run from display_firmware/; safe to run again)

The id of a page is its position in project.json, so a new order changes the numbers. This tool changes together:

* project.json (the page list: the keys and the paths), the page files (renamed, ``name`` inside them), the names of pages in the event code
  (``page <name>``, ``<name>.<object>``), ``Program.s`` (``${page:...}``);
* the page numbers that the code of a page writes as literals (``prints 0x65,1`` followed by a number, ``prints 113,1`` followed by a number): in the pages and in
  the saved sources of the generator (``tools/migration_sources/``, they keep the stock names);
* librescreen/screen/pageids.py: the number of every page;
* tools/migrated.json (the hashes of the page files).
tests/e2e/golden has to be recorded again, and the pages that name another page in the host (``preview.cp_data``) are renamed by hand once.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import page_names as names
from renumber import remap_node, save

ROOT = names.ROOT
PAGEIDS = ROOT.parent / "librescreen" / "screen" / "pageids.py"


def main():
    project = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
    current = [p["key"] for p in project["pages"]]
    final = [names.new(k) for k in current]
    if sorted(final) != sorted(names.ORDER):
        sys.exit("the order of mockup/pages.json does not hold exactly the pages of the project: %s" % sorted(set(final) ^ set(names.ORDER)))
    new_id = {i: names.ORDER.index(final[i]) for i in range(len(current))}

    # pageids.py: the decimal constants are the ids of the pages
    page_line = re.compile(r"^([A-Z_0-9]+) = (\d+)(\s*#.*)?$")
    out = []
    for line in PAGEIDS.read_text(encoding="utf-8").split("\n"):
        m = page_line.match(line)
        if m:
            line = "%s = %d%s" % (m.group(1), new_id[int(m.group(2))], m.group(3) or "")
        out.append(line)
    PAGEIDS.write_text("\n".join(out), encoding="utf-8")

    done = json.loads((ROOT / "tools" / "migrated.json").read_text(encoding="utf-8"))
    for i, key in enumerate(current):
        name = final[i]
        source = ROOT / "pages" / (key + ".json")
        data = remap_node(json.loads(source.read_text(encoding="utf-8")), new_id)
        data = names.rename_refs(data)
        data["name"] = name
        target = ROOT / "pages" / (name + ".json")
        save(target, data, 1)
        if source != target:
            source.unlink()
    for path in sorted((ROOT / "tools" / "migration_sources").glob("*.json")):      # the sources keep the stock names, their numbers follow
        save(path, remap_node(json.loads(path.read_text(encoding="utf-8")), new_id), 1)
    entries = {p["key"]: p for p in project["pages"]}
    project["pages"] = [{**entries[current[final.index(n)]], "key": n, "content": {"mode": "json", "path": "pages/%s.json" % n}} for n in names.ORDER]
    save(ROOT / "project.json", project, 2)
    for stock_name, entry in done.items():
        path = ROOT / names.page_file(stock_name)
        if path.exists():
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    save(ROOT / "tools" / "migrated.json", done, 1)
    program = ROOT / "Program.s"
    text = program.read_text(encoding="utf-8")
    for old, new in names.NEW.items():
        text = text.replace("${page:%s}" % old, "${page:%s}" % new)
    program.write_text(text, encoding="utf-8")
    print("%d pages named and ordered" % len(names.ORDER))


if __name__ == "__main__":
    main()
