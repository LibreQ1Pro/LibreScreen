"""Collects every tile that the stock sheets stand for (see tile_core.py): the static looks of the widgets, the looks
the screen's own code sets and the looks the host sets (tile_spec.py)."""
import collections
import re

import tile_core as core
from tile_spec import SPEC

# ``obj.picc=${picture:K}`` / ``obj.picc2==${picture:K}`` inside the event code
REFERENCE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.(picc2?)(==?)\$\{picture:([A-Za-z0-9_]+)\}")
CROPPED = ("button", "text", "crop_picture")


def event_blocks(node, path=()):
    """Every list of code lines of a page: yields (path, list)."""
    if isinstance(node, list) and node and all(isinstance(x, str) for x in node):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from event_blocks(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from event_blocks(value, path + (i,))


class Plan(object):
    def __init__(self, project):
        self.project = project
        self.tiles = {}                         # digest -> {"image", "uses": [(page, widget, sheet, role)]}
        self.of = {}                            # (page, widget, sheet) -> digest
        self.raw = {}                           # (page, widget, sheet) -> the tile before its corners were cleared
        self.static = {}                        # (page, widget) -> {"picc": digest, "picc2": digest}
        self.dynamic = set()                    # (page, widget) whose look changes while the screen runs
        self.states = collections.defaultdict(dict)    # (widget, state) -> {page: (digest, digest or None)}
        self.script_uses = []
        self.problems = []
        self.collect()

    def tile(self, page, widget, sheet, role):
        """Name (digest) of the tile of ``widget`` for ``sheet`` (None: the widget shows no sheet)."""
        key = (page, widget, sheet)
        if key not in self.of:
            obj = self.project.widget(page, widget)
            rect = core.rect_of(obj)
            image, _, raw = core.cut(self.project, page, rect, sheet)
            self.raw[key] = raw
            name = core.digest(image)
            if core.is_blank(image):
                name = "blank_%dx%d" % image.size
            self.tiles.setdefault(name, {"image": image, "uses": []})
            self.of[key] = name
        self.tiles[self.of[key]]["uses"].append((page, widget, sheet, role))
        return self.of[key]

    def collect(self):
        project = self.project
        for page, group, widgets, states in SPEC:
            for widget in widgets:
                self.dynamic.add((page, widget))
                for state, (normal, pressed) in states.items():
                    one = self.tile(page, widget, normal, "state:%s:%s" % (group, state))
                    two = self.tile(page, widget, pressed, "state:%s:%s:press" % (group, state)) if pressed else None
                    self.states[(widget, state)][page] = (one, two)
        for page, data in project.pages.items():
            for path, lines in event_blocks(data):
                for line in lines:
                    for m in REFERENCE.finditer(line):
                        widget, attr, op, sheet = m.groups()
                        self.dynamic.add((page, widget))
                        digest = self.tile(page, widget, sheet, "script:" + attr)
                        self.script_uses.append((page, widget, attr, op, sheet, digest))
        for page, data in project.pages.items():
            for obj in data["objects"]:
                a = obj["attributes"]
                if obj["type"] not in CROPPED or (obj["type"] != "crop_picture" and a.get("sta") != 0):
                    continue
                sheets = {attr: core.ref_key(a.get(attr)) for attr in ("picc", "picc2")}
                if not any(sheets.values()):
                    continue
                if obj["type"] == "crop_picture":
                    sheets.pop("picc2")
                if not core.inside(core.rect_of(obj)):
                    self.problems.append("%s.%s is off the screen" % (page, obj["key"]))
                    self.static[(page, obj["key"])] = {}
                    continue
                # a sheet that is not there shows nothing: the background (with the button drawn into it) stays
                self.static[(page, obj["key"])] = {
                    attr: self.tile(page, obj["key"], sheet, "static:" + attr) for attr, sheet in sheets.items()}
