#!/usr/bin/env python3
"""Every widget the host writes to (``g.port.txt("name", ...)``, ``val``, ``pco``, ``vis``, ``tsw``, ``face``) has to exist on some page of the screen project.

    python3 tools/check_host_names.py          (run from display_firmware/)

A literal first argument is looked up (``page.name`` forms: the name after the dot); built names (``"row" + n + "_txt"``) are not checked. This is the static
part of what tests/e2e checks while a scenario runs.
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METHODS = {"txt", "val", "pco", "vis", "tsw", "face", "cp_close", "cp_image"}


def widgets():
    names = set()
    for path in (ROOT / "pages").glob("*.json"):
        names.update(o["attributes"]["objname"] for o in json.loads(path.read_text(encoding="utf-8"))["objects"])
    return names


def problems():
    """The writes of the host to a widget that no page has: ["file:line  method('name')", ...]."""
    have, problems = widgets(), []
    for path in sorted((ROOT.parent / "librescreen").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in METHODS and node.args:
                owner = node.func.value
                if not (isinstance(owner, ast.Attribute) and owner.attr == "port") or not isinstance(node.args[0], ast.Constant):
                    continue
                name = str(node.args[0].value).split(".")[-1]
                if name.isidentifier() and name not in have and name not in ("255",):
                    problems.append("%s:%d  %s(%r)" % (path.relative_to(ROOT.parent), node.lineno, node.func.attr, node.args[0].value))
    return problems


def main():
    found = problems()
    for line in found:
        print(line)
    print("%d problems" % len(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
