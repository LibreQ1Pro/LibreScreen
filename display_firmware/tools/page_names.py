"""The names and the order of the pages of the screen project.

``mockup/pages.json`` holds the table stock name -> readable name (``pages``) and the order of the pages (``order``: the flow of using the printer: boot, setup, home,
filament, move, files, printing, calibration, settings, network, errors). The id of a page is its position in project.json, so the order is the numbering.
The tools that make the pages keep the stock names as the *source* names (tools/migration_sources/, tools/migrated.json, the rules of tools/page_rules.py);
``page_file`` / ``rename_refs`` turn them into what the project holds.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TABLE = json.loads((ROOT / "mockup" / "pages.json").read_text(encoding="utf-8"))
MOCKUP = _TABLE["pages"]                    # stock name -> the readable name of the mockup (a page that keeps its name is not in it)
SHORT = _TABLE["short"]                     # the readable name of the mockup -> the name in the project (the editor takes at most 14 characters)
ORDER = [SHORT.get(n, n) for n in _TABLE["order"]]       # the names of the project, in the order of project.json
NEW = {old: SHORT.get(mockup, mockup) for old, mockup in MOCKUP.items()}      # stock name -> the name in the project
STOCK = {**{mockup: old for old, mockup in MOCKUP.items()}, **{new: old for old, new in NEW.items()}}


def new(name):
    """The project name of a page (a stock name, the name of the mockup, or already the project name)."""
    name = STOCK.get(name, name)
    return NEW.get(name, name)


def stock(name):
    """The stock (source) name of a page."""
    return STOCK.get(name, name)


def page_file(name):
    return "pages/%s.json" % new(name)


def _blocks(node):
    if isinstance(node, list) and node and all(isinstance(x, str) for x in node):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _blocks(value)
    elif isinstance(node, list):
        for value in node:
            yield from _blocks(value)


def rename_refs(node):
    """In the event code of a page: ``page <name>``, ``${page:<name>}`` and ``<name>.<object>`` name the pages by their names in the project."""
    changed = {old: new_name for old, new_name in NEW.items() if old != new_name}
    patterns = []
    for old, new_name in changed.items():
        patterns.append((re.compile(r"(?<![\w.$])page\s+%s\b" % re.escape(old)), "page " + new_name))
        patterns.append((re.compile(r"(?<![\w.$])%s\.(?=[A-Za-z_])" % re.escape(old)), new_name + "."))
        patterns.append((re.compile(r"\$\{page:%s\}" % re.escape(old)), "${page:%s}" % new_name))
    for lines in _blocks(node):
        for i, line in enumerate(lines):
            for pattern, text in patterns:
                line = pattern.sub(text, line)
            lines[i] = line
    return node
