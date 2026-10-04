#!/usr/bin/env python3
"""Removes pages from the screen project and renumbers the rest: the project, the page ids of the host and the page numbers inside the event code.

    python3 tools/renumber.py KEY [KEY ...]            (run from display_firmware/; refuses a key that is not a page)

The id of a page is its position in project.json. Removing a page moves every page after it, so this tool changes together:

* project.json (the page list) and the page files, the pages of ``tools/migration_sources/`` (the source of the generator) and ``tools/migrated.json``;
* librescreen/screen/pageids.py: the block of the removed page goes, the number of every other page is its new position;
* the page numbers that the code of a page writes as literals: ``prints 0x65,1`` followed by a page number (the sleep timer, the language pages) and
  ``prints 113,1`` (the value frames of the keyboards) followed by the page of the value;
* mockup/pages.json (the readable names) and tests/e2e/golden is recorded again by hand afterwards.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import page_names  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGEIDS = ROOT.parent / "librescreen" / "screen" / "pageids.py"


def remap_lines(lines, mapping):
    out = list(lines)
    for i, line in enumerate(out[:-1]):
        if line.strip() in ("prints 0x65,1", "prints 113,1"):
            m = re.match(r"^(\s*)prints (\d+),1$", out[i + 1])
            if m and int(m.group(2)) in mapping:
                out[i + 1] = "%sprints %d,1" % (m.group(1), mapping[int(m.group(2))])
    return out


def remap_node(node, mapping):
    if isinstance(node, list) and node and all(isinstance(x, str) for x in node):
        return remap_lines(node, mapping)
    if isinstance(node, dict):
        return {k: remap_node(v, mapping) for k, v in node.items()}
    if isinstance(node, list):
        return [remap_node(v, mapping) for v in node]
    return node


def save(path, data, indent):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def main():
    removed = sys.argv[1:]
    if not removed:
        sys.exit(__doc__)
    project = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
    keys = [p["key"] for p in project["pages"]]
    for key in removed:
        if key not in keys:
            sys.exit("%s is not a page" % key)
    kept = [k for k in keys if k not in removed]
    old_id = {k: i for i, k in enumerate(keys)}
    new_id = {k: i for i, k in enumerate(kept)}
    mapping = {old_id[k]: new_id[k] for k in kept}

    # pageids.py: the constant of a page (``NAME = number``) starts a part that ends at the next page constant; the part of a removed page goes
    page_line = re.compile(r"^([A-Z_0-9]+) = (\d+)(\s*#.*)?$")
    out, skip = [], False
    for line in PAGEIDS.read_text(encoding="utf-8").split("\n"):
        m = page_line.match(line)
        if m:
            number = int(m.group(2))
            skip = keys[number] in removed
            if not skip:
                line = "%s = %d%s" % (m.group(1), mapping[number], m.group(3) or "")
        if not skip:
            out.append(line)
    PAGEIDS.write_text("\n".join(out), encoding="utf-8")

    # pages and sources
    for folder in (ROOT / "pages", ROOT / "tools" / "migration_sources"):
        for path in sorted(folder.glob("*.json")):
            key = path.stem
            if key in removed:
                path.unlink()
                continue
            save(path, remap_node(json.loads(path.read_text(encoding="utf-8")), mapping), 1)
    project["pages"] = [p for p in project["pages"] if p["key"] not in removed]
    save(ROOT / "project.json", project, 2)
    done = json.loads((ROOT / "tools" / "migrated.json").read_text(encoding="utf-8"))
    import hashlib
    for key in list(done):                    # migrated.json is keyed by the stock name; "design" is the page of the project
        if key in removed or done[key].get("design", key) in removed:
            del done[key]
    for key, entry in done.items():           # the page files changed (their numbers): what the generator checks against changes with them
        entry["sha256"] = hashlib.sha256((ROOT / page_names.page_file(key)).read_bytes()).hexdigest()
    save(ROOT / "tools" / "migrated.json", done, 1)
    names = json.loads((ROOT / "mockup" / "pages.json").read_text(encoding="utf-8"))
    for key in removed:
        names["pages"].pop(key, None)
    save(ROOT / "mockup" / "pages.json", names, 1)
    print("removed %s; %d pages left" % (", ".join(removed), len(kept)))


if __name__ == "__main__":
    main()
