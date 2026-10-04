#!/usr/bin/env python3
"""Rebuild pages of the screen project from the mockup (mockup/spec.json), keeping the behaviour of the stock page.

    python3 tools/migrate_pages.py PAGE [PAGE ...]       stock or new names
    python3 tools/migrate_pages.py --family popups       a named group (tools/page_rules.py)
    python3 tools/migrate_pages.py --report              what is migrated

The engine is generic; whatever it cannot decide it refuses (it never drops code silently):

* a stock component that the mockup does not draw must be named in the rules (``drop``), else the page is refused;
* a line of event code that names a component of the stock page that is not on the new page is an error too;
* every widget of the mockup that the stock page lacks is created without code and listed (``new``): the host needs it or it is decoration.

What a page is made of, in the order of the mockup (z):

* the page colour is ``sta=1`` + ``bco`` (a full-screen fill of the mockup is the colour);
* a *decor* piece (a card, a panel, a pill, an icon, art) is a ``picture`` that is a crop of the static rendering of the mockup
  (``index.html?bare=ID&static=1``: no run-time text, no thumbnails): the corners hold what lies under them, so no alpha is needed;
  the crop also holds whatever the mockup draws over it that does not change (an icon on a card);
* an interactive widget (a button, a key, a row, a navigation item) is a ``button`` with ``pic`` (released) and ``pic2`` (pressed:
  the released tile darkened inside its rounded shape); a ``hit`` is a ``touch_hotspot``; a label is the ``txt`` of a centred button or a
  ``text`` of its own that forwards the touch to the button;
* a text is a ``text`` with the font of its role, the colour and the matte (the colour under it in the rendering);
* a widget the stock page has keeps its events by name (``aliases`` of the rules map a new name to a stock one);
* a text that the stock page did not have gets its translations from the mockup, into the ``if(lang==N)`` chain of ``codesload``.
"""
import argparse
import collections
import copy
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import gen_project as gp
import page_names
import page_patches as patches
from gen_project import ROOT, rgb565

sys.path.insert(0, str(ROOT / "tools"))
import page_rules as rules_mod                    # noqa: E402

SS = 4
LANG_COUNT = 13
INVISIBLE = ("timer", "variable", "touch_capture")
BG = (0x17, 0x17, 0x1a)


class Metrics:
    """The wrapping of the screen: the glyph widths of the fonts of the project (the emulator wraps the same way), so a text box can be given
    the height its longest translation needs."""
    CELL = {}

    def __init__(self):
        import tile_core
        tile_core.builder_path()
        import hmi_font
        self.fonts = {}
        for role in ("t13", "t16", "t19", "d20", "d28", "d32"):
            reader = hmi_font.FontReader((ROOT / "fonts" / ("font_%s.zi" % role)).read_bytes())
            self.fonts[role] = reader
            Metrics.CELL[role] = reader.height

    def advance(self, role, ch):
        glyph = self.fonts[role].glyph(ord(ch))
        return glyph["width"] if glyph else 4

    def lines(self, role, text, width):
        count = 0
        for paragraph in text.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
            current, used, last_space = "", 0, -1
            count += 1
            for ch in paragraph:
                adv = self.advance(role, ch)
                if used + adv > width and current:
                    count += 1
                    if last_space >= 0 and ch != " ":
                        current = current[last_space + 1:]
                    else:
                        current = ""
                    used = sum(self.advance(role, c) for c in current)
                    last_space = -1
                if ch == " ":
                    last_space = len(current)
                current += ch
                used += adv
        return count

    def height(self, role, texts, width):
        return max(self.lines(role, t, width) for t in texts) * Metrics.CELL[role]

    def wrap(self, role, text, width):
        """The lines of a text broken at the spaces for a box of ``width`` pixels (the screen itself breaks a line at the last letter that fits)."""
        out = []
        for paragraph in text.replace("\\r\\n", "\r").replace("\\r", "\r").replace("\r\n", "\r").replace("\n", "\r").split("\r"):
            # a line never starts or ends with a space: it would push a centred line to one side (the stock texts broke a line as "\r" + " ")
            paragraph = re.sub(" +", " ", paragraph.strip(" "))          # the stock breaks were "\r" + " ": joined, they left double spaces
            current, used, last_space = "", 0, -1
            for ch in paragraph:
                adv = self.advance(role, ch)
                if used + adv > width and current:
                    if last_space >= 0 and ch != " ":
                        out.append(current[:last_space])
                        current = current[last_space + 1:]
                    else:
                        out.append(current)
                        current = ""
                    used = sum(self.advance(role, c) for c in current)
                    last_space = -1
                    if ch == " ":
                        continue            # the space that did not fit is the break: the next line does not start with it
                if ch == " ":
                    last_space = len(current)
                current += ch
                used += adv
            out.append(current)
        return out


METRICS = Metrics()

# the attributes of an animation component that plays the animation ``spinner`` all the time (the stock components of the wizards, with the new resource)
SPINNER = {"drag": 0, "sendkey": 0, "aph": 127, "movex": 0, "movey": 0, "effect": 0, "first": 0, "time": 300, "lockobj": 0, "groupid0": 0, "groupid1": 0, "from": 0,
           "vid": {"$ref": "animation:spinner"}, "path": "", "path_m": 255, "en": 1, "loop": 1, "dis": 100, "tim": 0, "stim": 0, "qty": 0, "molloc_s": 12000, "molloc": 12000}


def host_names():
    """The names the host writes to (string literals of librescreen/), the names it builds (``row3_txt``) and the readout fields: these texts change at run time,
    so their box is solid (it erases the old text); every other text is written once by the page and is transparent (it can lie over a picture)."""
    import ast
    names = set()
    for path in (ROOT.parent / "librescreen").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r"[a-z_][a-z0-9_]*", node.value):
                names.add(node.value)
    for i in range(1, 6):
        names.update(["row%d_txt" % i])
    for i in range(1, 5):
        names.update(["file%d_name" % i])
    for i in range(1, 4):
        names.update(["fan%d_val" % i])
    for i in range(30):
        names.add("cell_%d" % i)
    return names


HOST_NAMES = host_names()


def spec_pages():
    spec = json.loads((ROOT / "mockup/spec.json").read_text(encoding="utf-8"))
    pages = collections.defaultdict(list)
    for item in spec:
        sided = {w["name"] for w in item["widgets"] if w["kind"] == "btn" and any(l.get("align") in ("l", "r") for l in w["labels"])}
        for group in [item["widgets"]] + [language["widgets"] for language in item["languages"].values()]:
            for widget in group:
                if widget["name"] in sided:
                    for label in widget["labels"]:
                        label["centered"] = False          # a button's own text is centred: a label that lies at one side is a text of its own
        pages[item["old"]].append(item)
    return pages


def mode_colour(image, rect):
    """The most common colour of a rectangle: the matte under a text."""
    crop = image.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]))
    colours = crop.getcolors(maxcolors=crop.width * crop.height)
    return max(colours)[1]


def contains(outer, inner):
    return (outer["x"] <= inner["x"] and outer["y"] <= inner["y"] and
            outer["x"] + outer["w"] >= inner["x"] + inner["w"] and outer["y"] + outer["h"] >= inner["y"] + inner["h"])


def darkened(image, factor=0.82):
    """The pressed look: the released tile darker (the alpha of the corners stays the one of the released tile)."""
    return gp.quantize(image.point(lambda v: round(v * factor)))


def rounded(image, mask):
    """The tile of a button with transparent corners (a PNG with alpha): what lies under the corners on the page shows through, also when the button is pressed.
    ``mask`` is the alpha that the browser draws for the button (the layer of the buttons of the mockup)."""
    return gp.round_tile(image, mask)


def lightened(image):
    """The pressed look of a button that has no fill of its own (the title bar: the arrow on the page colour): the bar gets a little lighter."""
    return gp.quantize(image.point(lambda v: min(255, v + 11)))


def esc(text):
    return text.replace("\\", "/").replace('"', "'").replace("\n", " ").strip()


def add_to_chain(lines, additions):
    """Puts lines into the ``if(lang==N)`` blocks of ``codesload`` (right after the ``{`` of the block, whatever the block holds); a language
    without a block gets one at the end."""
    out = list(lines)
    for lang in sorted(additions, reverse=True):
        new = ["  " + l.strip() for l in additions[lang]]
        header = next((i for i, l in enumerate(out) if re.match(r"^(?:\}else )?if\(lang==%d\)$" % lang, l.strip())), None)
        if header is not None and header + 1 < len(out) and out[header + 1].strip() == "{":
            out[header + 2:header + 2] = new
        else:
            out += ["if(lang==%d)" % lang, "{"] + new + ["}"]
    return out


def names_in(line):
    """Component names a line of code refers to (before the dot, outside strings)."""
    code = re.sub(r'"[^"]*"', '""', line)
    found = set(re.findall(r"(?<![\w.$])([A-Za-z_]\w*)\.(?:txt|val|pic|pic2|pco|pco2|bco|bco2|font|picc|picc2|en|tim|xcen|x|y|w|h)\b", code))
    found |= set(re.findall(r"\b(?:vis|tsw|click|ref)\s+([A-Za-z_]\w*)\s*,", code))
    found |= set(re.findall(r"\bp\[\d+\]\.b\[\d+\]", code))
    return found


def rename_refs(line, mapping):
    """Rewrite the names of components in a line of code (outside strings): ``old.attr`` and ``vis old,`` / ``click old,`` ..."""
    if not mapping:
        return line
    parts = re.split(r'("(?:[^"\\]|\\.)*")', line)
    for i in range(0, len(parts), 2):
        code = parts[i]
        for old, new in mapping.items():
            code = re.sub(r"(?<![\w.$])%s(?=\.)" % re.escape(old), new, code)
            code = re.sub(r"\b(vis|tsw|click|ref)(\s+)%s(?=\s*,)" % re.escape(old), r"\1\2" + new, code)
        parts[i] = code
    return "".join(parts)


class Migration:
    def __init__(self, old, project, tiles, rules):
        self.old, self.project, self.tiles, self.rules = old, project, tiles, rules
        self.spec = spec_pages()[old]
        self.base = self.spec[0]
        self.tiles.page = self.base["page"]          # the pictures are named after the page
        self.stock = gp.source_page(old)
        self.original = {o["attributes"]["objname"]: o for o in self.stock["objects"]}
        self.alias = rules.get("aliases", {})
        self.report = {"new": [], "kept": [], "dropped": [], "baked": 0}
        self.retarget = {}                       # stock component that lost its text -> the text widget that holds it now
        self.faces = {}                          # widget -> {state: [released, pressed]} for tools/faces.json
        self.decor_texts = []
        self.hidden = []                         # components of other variants of the screen: hidden until the screen / host shows them
        self.looks = {}                          # selectable widget -> {"on"/"off": (released, pressed)}
        self.shot = gp.screenshot(self.base["id"], self.base["variant"], 2)
        self.layer_names = [w["name"] for w in self.base["widgets"] if w["name"]]          # the widgets whose shape the layer of the buttons holds (the cards that are buttons too)
        # the decor holds what lies under the widgets that are components of their own (buttons, and the cards that are buttons too): not their pieces
        self.decor_shot = gp.screenshot(self.base["id"], self.base["variant"], 2, nobtn=True,
                                        hide=[w["name"] for w in self.base["widgets"] if w["name"] and self.is_interactive(w)],
                                        hidebox=[tuple(r["rect"]) for r in rules.get("regions", {}).values()])        # the regions are pictures of their own       # without the buttons: decor holds what lies under them
        self.chain = {}
        for line in self.stock["root"]["events"].get("codesload", []):
            m = re.match(r'^\s*(\w+)\.txt="(.*)"\s*$', line)
            if m:
                self.chain.setdefault(m.group(1), []).append(m.group(2).replace("\\r\\n", " ").replace("\\r", " "))

    # -- helpers ---------------------------------------------------------------------------------------------------
    def stock_of(self, name):
        return self.original.get(self.alias.get(name, name))

    def label_name(self, widget):
        names = self.rules.get("label_names", {})
        if widget["name"] in names:
            return names[widget["name"]]
        name = widget["name"].replace("_btn", "_lbl") if widget["name"].endswith("_btn") else widget["name"] + "_lbl"
        if len(name.encode()) > 14:
            name = widget["name"][:10] + "_lbl"
        return name

    def shot_of(self, widget, nobtn=False):
        """The rendering a widget is cut from: the base state of the page, or the variant that shows a widget the base lacks."""
        variant = widget.get("src_variant")
        if variant is None:
            return self.decor_shot if nobtn else self.shot
        return gp.screenshot(self.base["id"], variant, 2, nobtn=nobtn)

    def face(self, widget, fill):
        """(released, pressed) tiles of an interactive widget. A widget the screen / host selects has an ``off`` and an ``on`` look
        (rules ``selectable``: the variant or the language of the mockup that shows it unselected / selected); the default is ``off``."""
        rect = {k: widget[k] for k in ("x", "y", "w", "h")}
        box = (rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])

        def alpha(variant, lang=2):
            """The alpha of the button as the browser draws it (only a button that has a fill of its own has rounded corners; the others stay opaque)."""
            if not fill:
                return None
            mask = gp.screenshot(self.base["id"], variant, lang, layer=True, names=self.layer_names).crop(box).getchannel("A")
            # the fill is not a button of the HTML (nothing of it is in the layer): the tile stays opaque
            return mask if mask.getpixel((rect["w"] // 2, rect["h"] // 2)) == 255 else None

        selectable = self.rules.get("selectable", {}).get(widget["name"])
        if selectable:
            looks = {}
            for state, source in selectable.items():
                variant, lang = source.get("variant", self.base["variant"]), source.get("lang", 2)
                if source.get("blank"):
                    image = Image.new("RGB", (rect["w"], rect["h"]), tuple(source["blank"]))
                else:
                    image = gp.screenshot(self.base["id"], variant, lang).crop(box)
                mask = None if source.get("blank") else alpha(variant, lang)       # a blank look is opaque: it has to wipe the corners of the look it replaces
                suffix = "" if state == "off" else "_" + state
                looks[state] = (self.tiles.add(widget["name"] + suffix, rounded(image, mask)),
                                self.tiles.add(widget["name"] + suffix + "_press", rounded(darkened(image), mask)))
            self.looks[widget["name"]] = looks
            return looks["off" if "off" in looks else next(iter(looks))]
        image = self.shot_of(widget).crop(box)
        mask = alpha(widget.get("src_variant") or self.base["variant"])
        released = self.tiles.add(widget["name"], rounded(image, mask))
        pressed = self.tiles.add(widget["name"] + "_press", rounded(darkened(image), mask) if fill else lightened(image))
        return released, pressed

    def text_for(self, widget, label=None):
        return (label or widget).get("text", "")

    # -- the page --------------------------------------------------------------------------------------------------
    def run(self):
        rules, objects, used = self.rules, [], set()
        widgets = {w["name"]: w for w in self.base["widgets"] if w["name"]}
        # every variant adds its widgets that the base lacks (hidden until the screen / host shows them)
        extra = {}
        for variant in self.spec[1:]:
            for w in variant["widgets"]:
                if w["name"] and w["name"] not in widgets and w["name"] not in extra:
                    extra[w["name"]] = dict(w, src_variant=variant["variant"], src_prims=variant["prims"])
        all_widgets = {**widgets, **extra}
        for obj in self.stock["objects"]:
            if obj["type"] in INVISIBLE:
                objects.append(copy.deepcopy(obj))
                used.add(obj["attributes"]["objname"])
        bg = tuple(self.base["bg"])
        fills = [p for p in self.base["prims"] if p["prim"] == "fill"]
        for p in fills:
            if p["w"] >= 272 and p["h"] >= 480 and p["x"] <= 0 and p["y"] <= 0:
                bg = tuple(p["bg"])
        items = [("p", p["z"], p) for p in self.base["prims"]] + [("w", w["z"], w) for w in self.base["widgets"]]
        items += [("d", d["z"], d) for d in self.base["decor"]]
        items += [("e", w["z"], w) for w in extra.values()]
        items.sort(key=lambda t: (t[1], t[0]))

        emitted, faces = [], {}
        visual, labels_pending, texts_new = [], [], []
        regions = rules.get("regions", {})
        region_done = set()
        for kind, z, it in items:
            if kind == "p":
                if it["w"] >= 272 and it["h"] >= 480:
                    continue
                hit = next((n for n, r in regions.items() if contains(dict(zip("xywh", r["rect"])), it)), None)
                if hit:
                    if hit not in region_done:
                        region_done.add(hit)
                        visual.append(self.region(hit, regions[hit]))
                    continue
                if any(contains(e, it) and ez < z for ez, e in emitted):
                    self.report["baked"] += 1
                    continue
                owner = it.get("owner")
                if owner and self.is_interactive(widgets.get(owner)):
                    continue                    # the face of the interactive widget holds it
                # the editor does not take a component thinner than 2 pixels: a one pixel rule is cut with the pixel under (or beside) it, which the rendering has
                it = dict(it, w=max(it["w"], 2), h=max(it["h"], 2))
                key = self.tiles.add("decor", self.decor_shot.crop((it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])))
                name = "bg%d" % z
                for pname, entry in rules.get("pictures", {}).items():
                    if [it["x"], it["y"], it["w"], it["h"]] == entry["rect"]:
                        name = pname
                        self.state_pictures(pname, it, entry)
                visual.append(gp.component("picture", name, it["x"], it["y"], it["w"], it["h"], pic=gp.pic_ref(key)))
                emitted.append((z, it))
            elif kind == "d":
                name = rules.get("decor_names", {}).get(it["text"].strip(), "lbl%d" % z)
                it = dict(it, name=name)
                texts_new.append(it)
                self.decor_texts.append(it)
                visual.append(self.text_object(it, name, stock=None, dyn=False))
            else:
                before = len(visual)
                self.widget(it, visual, emitted, faces, labels_pending)
                if kind == "e":
                    self.hidden += [o["attributes"]["objname"] for o in visual[before:]]
        for name, entry in regions.items():            # a region the base state of the design does not draw (the mark of the last printed file) lies on top
            if name not in region_done:
                region_done.add(name)
                visual.append(self.region(name, entry))
        # components that the stock page has and the mockup never draws
        placed = {o["attributes"]["objname"] for o in objects + visual}
        for name, obj in self.original.items():
            if name in placed or obj["type"] in INVISIBLE:
                continue
            if name in rules.get("keep", []):
                keep = copy.deepcopy(obj)
                if isinstance(keep["attributes"].get("font"), dict) and keep["attributes"]["font"]["$ref"] in ("font:font_title18", "font:font_small14", "font:font_digits24"):
                    keep["attributes"]["font"] = {"$ref": "font:font_t16"}      # the fonts of the stock design are gone
                visual.append(keep)
                continue
            if name in rules.get("drop", []):
                self.report["dropped"].append(name)
                continue
            if name in {self.alias.get(n, n) for n in all_widgets}:
                continue
            raise ValueError("%s: the stock component %s (%s) is not drawn by the mockup: put it into rules keep / drop" % (self.old, name, obj["type"]))
        for wname, looks in self.looks.items():
            self.faces[wname] = {state: list(pair) for state, pair in looks.items()}
        objects += visual
        gone = set(self.original) - {o["attributes"]["objname"] for o in objects}
        self.stock["objects"] = objects
        self.stock["root"]["attributes"].update(sta=1, bco=rgb565(bg), pic=65535)
        self.finish_events(gone, all_widgets)
        self.break_lines()
        gp.save(page_names.page_file(self.old), self.stock)
        gp.record(self.old, {"design": self.base["page"], "adapter": "migrate_pages", **{k: v for k, v in self.report.items()}})
        return self.report

    def is_interactive(self, widget):
        if widget is None:
            return False
        if widget["kind"] in ("btn", "key", "rowhit", "hit"):
            return True
        if widget["name"] in self.rules.get("actions", {}):
            return True
        stock = self.stock_of(widget["name"])
        return bool(stock and stock["type"] in ("button", "touch_hotspot") and (stock["events"].get("codesup") or stock["events"].get("codesdown")))

    def text_object(self, w, name, stock, dyn):
        """A text widget; the matte is what the rendering shows under it."""
        w = dict(w)
        slot_height = w["h"]
        if not dyn and w.get("role") in Metrics.CELL:
            # a static text is as tall as its longest translation needs (the glyph widths and the cell of its font), and no taller: the box is solid or
            # transparent but never covers a neighbour, and no line of any language is cut
            texts = [x.get("text") or "" for x in self.spec_widgets(name)] or [w.get("text", "")]
            texts += self.chain.get(self.alias.get(name, name), []) + w.get("all_texts", [])
            texts += [d["text"] for li in range(LANG_COUNT) for d in self.spec[0]["languages"][str(li)]["decor"] if d["z"] == w.get("z")]
            need = METRICS.height(w["role"], texts, w["w"]) + 2
            single = w["h"] < 2 * Metrics.CELL[w["role"]]
            if single:
                need = Metrics.CELL[w["role"]] + 2
            if need > w["h"] or (not single and need != w["h"]):
                grow = need - w["h"]
                w["y"] += 0 if w.get("top") else -(grow // 2) if not w.get("bottom") else -grow
                w["h"] = need
        w["matte"] = list(mode_colour(self.shot_of(w), w))
        host = (name in HOST_NAMES and not (name == "title" and self.old != "wifi_kb")) or name.endswith(("_temp", "_set", "_pos", "_val")) or w.get("role") in ("d20", "d28", "d32")
        if dyn and w.get("role") in ("d20", "d28", "d32"):
            text = "---"                  # a value the host has not set yet (the digit fonts have "-")
        elif dyn and name.endswith("_set"):
            text = "/ ---"
        else:
            text = "" if dyn else (esc(stock["attributes"].get("txt", "")) if stock else esc(w.get("text", "")))
            if text in ("NULL", "newtxt"):
                text = "---"                  # the placeholder of the stock page: a value the host has not set yet
        obj = gp.text_component(w, name, text)
        obj["attributes"].update(sta=3, bco=65535)           # no background of its own: the picture or the page under it shows (a box of a matte would show as a frame)
        # A scrolling text (type 55) has no layout in the portable project, so a long message is a plain wrapped text: the host cuts it
        # to what fits (librescreen/screen/text.py fit_lines) and the full message stays in its log.
        a = obj["attributes"]
        a["isbr"] = 0 if w.get("role") in Metrics.CELL and slot_height < 2 * Metrics.CELL[w["role"]] and not w.get("top") else 1
        a["ycen"] = 0 if w.get("top") else 2 if w.get("bottom") else 1
        if stock:
            obj["events"] = copy.deepcopy(stock["events"])
            if stock["attributes"].get("key", 255) != 255:
                obj["attributes"]["key"] = stock["attributes"]["key"]      # a value bound to the keyboard stays bound
            self.report["kept"].append(name)
        else:
            self.report["new"].append(name)
        return obj

    def widget(self, w, visual, emitted, faces, labels_pending):
        name, kind = w["name"], w["kind"]
        if self.original.get(name, {}).get("type") in INVISIBLE:
            return                                  # the page's own timer / variable / touch capture of that name (the mockup draws its area)
        stock = self.stock_of(name)
        prims = w.get("src_prims", self.base["prims"])
        fill = next((p for p in prims if p["prim"] == "fill" and p.get("name") == name), None)
        if fill is None:         # a button without a name of its own fill: the fill that belongs to it (``owner``) and has its rectangle, with the radius of the HTML
            fill = next((p for p in prims if p["prim"] == "fill" and p.get("owner") == name and all(p[k] == w[k] for k in ("x", "y", "w", "h"))), None)
        if kind == "t":
            if stock is None:
                mode, text = self.classify(name, w)
                obj = self.text_object(w, name, None, dyn=False)
                obj["attributes"]["txt"] = text
                visual.append(obj)
                return
            dyn = bool(w.get("dyn")) or w["role"] in ("d20", "d28", "d32") or stock["attributes"].get("txt", "") == ""
            visual.append(self.text_object(w, name, stock, dyn))
            return
        if kind == "anim" and name == "spin" and stock is None:
            # the loading spinner of the waiting pages: the animation of the project (tools/make_spinner.py), frames as opaque as the page
            comp = {"key": name, "type": "animation", "attributes": {"objname": name, "vscope": 0, "x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"], **SPINNER},
                    "events": {"codesdown": [], "codesup": [], "codesplayend": []}}
            visual.append(comp)
            self.report["new"].append(name)
            return
        if kind in ("thumb", "anim", "bar") and stock is not None:
            comp = copy.deepcopy(stock)
            comp["attributes"].update({k: w[k] for k in ("x", "y", "w", "h")})
            if kind == "thumb" and fill:
                key = self.tiles.add("thumb_bg", self.shot.crop((w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"])))
                visual.append(gp.component("picture", name + "_bg", w["x"], w["y"], w["w"], w["h"], pic=gp.pic_ref(key)))
            if kind == "bar":
                self.style_bar(comp, w)
            visual.append(comp)
            self.report["kept"].append(name)
            emitted.append((w["z"], w))
            return
        if kind in ("thumb", "anim", "bar", "box") and stock is None:
            if fill or w.get("art"):
                key = self.tiles.add(name, self.shot.crop((w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"])))
                visual.append(gp.component("picture", name, w["x"], w["y"], w["w"], w["h"], pic=gp.pic_ref(key)))
                emitted.append((w["z"], w))
            return
        if kind == "hit" and stock is not None and stock["type"] == "slider":
            # a native slider: the track is ``ch`` percent of the height, the cursor a circle (psta 0), the ends are round (dis 100)
            comp = copy.deepcopy(stock)
            comp["attributes"].update({k: w[k] for k in ("x", "y", "w", "h")})
            comp["attributes"].update(sta=1, psta=0, wid=28, hig=28, dis=100, ch=round(10 * 100 / w["h"]), pic=65535, picc=65535, picc1=65535, pic1=65535, pic2=65535,
                                      bco=rgb565((41, 40, 49)), bco1=rgb565((57, 121, 255)), pco=rgb565((255, 255, 255)))
            visual.append(comp)
            emitted.append((w["z"], w))
            self.report["kept"].append(name)
            return
        if kind == "hit":
            comp = gp.component("touch_hotspot", name, w["x"], w["y"], w["w"], w["h"])
            if stock is not None:
                comp["events"] = copy.deepcopy(stock["events"])
                self.report["kept"].append(name)
            else:
                self.report["new"].append(name)
                self.give_action(comp)
            visual.append(comp)
            self.add_labels(w, visual, name)
            if stock is not None and stock["type"] == "button" and stock["attributes"].get("txt") and len(w["labels"]) == 1:
                self.retarget[self.alias.get(name, name)] = self.label_name(w)
            return
        # btn / key / card / rowhit / nav item
        interactive = self.is_interactive(w) or (stock is not None and stock["type"] == "button")
        if interactive or kind in ("btn", "key", "rowhit"):
            released, pressed = self.face(w, fill)
            comp = gp.component("button", name, w["x"], w["y"], w["w"], w["h"], sta=2, style=0, borderw=0, picc=65535, picc2=65535,
                                pic=gp.pic_ref(released), pic2=gp.pic_ref(pressed), font={"$ref": "font:font_t16"}, txt="", txt_maxl=1,
                                xcen=1, ycen=1, pco=rgb565((247, 247, 247)), pco2=rgb565((247, 247, 247)))
            if stock is not None:
                comp["events"] = copy.deepcopy(stock["events"])
                self.report["kept"].append(name)
            else:
                self.report["new"].append(name)
                self.give_action(comp)
            own = len(w["labels"]) == 1 and kind in ("btn", "key") and w["labels"][0].get("centered", True)
            if own:
                self.own_label(comp, w, w["labels"][0], stock)
            visual.append(comp)
            emitted.append((w["z"], w))
            if not own:
                self.add_labels(w, visual, name)
                if stock is not None and stock["type"] == "button" and len(w["labels"]) == 1 and (stock["attributes"].get("txt") or self.alias.get(name, name) in self.chain):
                    self.retarget[self.alias.get(name, name)] = self.label_name(w)
            return
        # a card without behaviour
        key = self.tiles.add(name, self.decor_shot.crop((w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"])))
        visual.append(gp.component("picture", name, w["x"], w["y"], w["w"], w["h"], pic=gp.pic_ref(key)))
        emitted.append((w["z"], w))
        self.report["new"].append(name) if stock is None else self.report["kept"].append(name)

    def new_picture(self, line, owner, ev):
        """``W.pic=${picture:KEY}`` and ``W.pic==${picture:KEY}`` of the stock design -> the look of W that the rules say KEY stood for
        (``picture_states``: a dict or a function of KEY -> the name of a state of ``selectable``)."""
        states = self.rules.get("picture_states")

        def one(m):
            widget, attr, op, key = m.groups()
            if states is None or widget not in self.looks:
                raise ValueError("%s: %s.%s uses a picture of the stock design, say in the rules what it stands for: %s" % (self.old, owner, ev, line))
            state = states(key) if callable(states) else states[key]
            return "%s.%s%s${picture:%s}" % (widget, attr, op, self.looks[widget][state][0 if attr == "pic" else 1])
        return re.sub(r"(\w+)\.(pic2?)(==?)\$\{picture:(\w+)\}", one, line)

    def break_lines(self):
        """The screen breaks a long text at the last letter that fits, not at a space: the line breaks (``\\r``) of every text that wraps are put in here, at the
        spaces, for the real glyph widths and the width of the widget (the text of the page, and what the chain of the page writes into it)."""
        def role_of(a):
            font = a.get("font")
            ref = font.get("$ref", "") if isinstance(font, dict) else ""
            return ref.split("font_")[-1] if "font_" in ref else None

        boxes = {}
        for o in self.stock["objects"]:
            a = o["attributes"]
            if o["type"] in ("text", "button") and a.get("isbr") == 1 and role_of(a) in Metrics.CELL and a.get("w"):
                boxes[a["objname"]] = (role_of(a), a["w"], a)

        def broken(role, width, text, height=None):
            lines = METRICS.wrap(role, text, width)
            allowed = max(1, height // Metrics.CELL[role]) if height else None
            if allowed and len(lines) > allowed:
                # more lines than the box has: the last words are shortened ("Cooling fan" -> "Cooling f.") until the text fits
                words = text.replace("\\r", " ").split(" ")
                for index in range(len(words) - 1, -1, -1):
                    while len(words[index].rstrip(".")) > 2 and len(METRICS.wrap(role, " ".join(words), width)) > allowed:
                        words[index] = words[index].rstrip(".")[:-1] + "."
                    if len(METRICS.wrap(role, " ".join(words), width)) <= allowed:
                        break
                lines = METRICS.wrap(role, " ".join(words), width)
            return "\\r".join(lines)

        for name, (role, width, a) in boxes.items():
            if a.get("txt"):
                a["txt"] = broken(role, width, a["txt"], a.get("h"))
                a["txt_maxl"] = max(a.get("txt_maxl", 10), len(a["txt"].encode()) + 8)
        pattern = re.compile(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\.txt="(.*)"(\s*)$')

        def convert(lines):
            out = []
            for line in lines:
                m = pattern.match(line)
                if m and m.group(2) in boxes:
                    role, width, a = boxes[m.group(2)]
                    line = '%s%s.txt="%s"%s' % (m.group(1), m.group(2), broken(role, width, m.group(3), a.get("h")), m.group(4))
                    a["txt_maxl"] = max(a.get("txt_maxl", 10), len(m.group(3).encode()) * 3 + 8)
                out.append(line)
            return out

        for events in [self.stock["root"]["events"]] + [o["events"] for o in self.stock["objects"]]:
            for ev, lines in events.items():
                events[ev] = convert(lines)

    def region(self, name, entry):
        """One picture for a part of the page that the mockup draws as several pieces and changes by state (the steps of a wizard)."""
        x, y, w, h = entry["rect"]
        rect = {"x": x, "y": y, "w": w, "h": h}
        self.state_pictures(name, rect, entry, isolate=True)
        first = next(iter(entry["states"]))
        default = self.faces[name][entry.get("default", first)][0]
        return gp.component("picture", name, x, y, w, h, pic=gp.pic_ref(default))

    def state_pictures(self, name, rect, entry, isolate=False):
        """The looks of a picture the host or the screen switches (``face(name, state)``): the same rectangle of another variant of the screen.
        ``isolate``: a region (the steps of a wizard) holds only its own pieces, not what the widgets beside it draw into the same rectangle."""
        looks = {}
        for state, variant in entry["states"].items():
            hide = []
            if isolate:
                shown = next((s for s in self.spec if s["variant"] == variant), self.base)
                hide = [w["name"] for w in shown["widgets"] if w["name"]]
            shot = gp.screenshot(self.base["id"], variant, 2, hide=hide)
            image = shot.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]))
            if entry.get("alpha"):
                image = gp.to_alpha(image, entry["alpha"])          # an icon over a button or a card: no background of its own
            looks[state] = [self.tiles.add("%s_%s" % (name, state), image), None]
        self.faces[name] = looks

    def spec_widgets(self, name):
        return [x for li in range(LANG_COUNT) for x in self.spec[0]["languages"][str(li)]["widgets"] if x["name"] == name]

    def texts_by_language(self, name, key="text"):
        out = {}
        for li in range(LANG_COUNT):
            entry = next((x for x in self.spec[0]["languages"][str(li)]["widgets"] if x["name"] == name), None)
            if entry is not None:
                out[li] = entry[key]
        return out

    def classify(self, name, w):
        """A text the stock page lacks: a *value* (it has digits or digit font: the host or the screen sets it, it starts as ``---``), a *constant*
        (the same in every language) or a *translated* text (``None``: the chain of ``codesload`` sets it)."""
        text = esc(w.get("text", ""))
        if w.get("dyn") or w.get("role") in ("d20", "d28", "d32") or re.search(r"\d", text):
            return "value", ("/ ---" if text.startswith("/") or name.endswith("_set") else "---")
        texts = set(esc(t) for t in self.texts_by_language(name).values())
        if len(texts) <= 1:
            return "constant", text
        return "translated", esc(self.texts_by_language(name).get(2, text))

    @staticmethod
    def line_language(lines, index):
        """The language a line of the ``codesload`` chain belongs to (the last ``if(lang==N)`` header before it)."""
        for i in range(index, -1, -1):
            m = re.match(r"^(?:\}else )?if\(lang==(\d+)\)$", lines[i].strip())
            if m:
                return int(m.group(1))
        return None

    def label_text(self, name, li):
        entry = next((x for x in self.spec[0]["languages"][str(li)]["widgets"] if x["name"] == name), None)
        return entry["labels"][0]["text"] if entry and entry["labels"] else ""

    def give_action(self, comp):
        """A widget that the stock page lacks sends the action the rules give it: ``65 <page> <action> ff ff ff``
        (``actions``: {widget: id} or {widget: {"id": n, "pre": [lines run first]}})."""
        action = self.rules.get("actions", {}).get(comp["attributes"]["objname"])
        if action is None:
            return
        pre = []
        if isinstance(action, dict):
            action, pre = action["id"], list(action.get("pre", []))
        comp["events"]["codesup"] = pre + ["prints 0x65,1", "prints dp,1", "prints %d,1" % action] + ["prints 0xff,1"] * 3

    def own_label(self, comp, w, label, stock):
        a = comp["attributes"]
        a.update(font={"$ref": "font:font_" + label["role"]}, pco=rgb565(label["color"] or (247, 247, 247)), pco2=rgb565(label["color"] or (247, 247, 247)),
                 txt=esc(label["text"]) if (stock is None or w["kind"] == "key" or not stock["attributes"].get("txt")) else esc(stock["attributes"].get("txt", "")),
                 txt_maxl=max(10, len(esc(label["text"]).encode()) * 3 + 8),
                 isbr=1 if w["h"] > 36 and w["kind"] != "key" else 0)
        if w["kind"] == "key":
            a["txt_maxl"] = 4

    def add_labels(self, w, visual, button_name):
        for label in w["labels"]:
            lname = self.label_name(w) if len(w["labels"]) == 1 else "%s_lbl%d" % (button_name, w["labels"].index(label))
            stock = self.original.get(lname)
            lab = dict(label)
            lab.update(role=label["role"])
            owner_texts = [self.label_text(button_name, li) for li in range(LANG_COUNT)]
            lab["all_texts"] = [t for t in owner_texts if t] or [label["text"]]
            obj = self.text_object(lab, lname, stock, dyn=False)
            obj["events"] = {"codesdown": ["click %s,1" % button_name], "codesup": ["click %s,0" % button_name]}
            visual.append(obj)

    def style_bar(self, comp, w):
        a = comp["attributes"]
        a.update(sta=0, bco=rgb565((41, 40, 49)), pco=rgb565((57, 121, 255)))

    # -- code ------------------------------------------------------------------------------------------------------
    def finish_events(self, gone, widgets):
        rules = self.rules
        root = self.stock["root"]["events"]
        # translations of new text widgets (the ones that differ by language)
        new_text = {}
        for name, w in widgets.items():
            known = self.original.get(self.alias.get(name, name))
            if known is not None and (known["type"] != "button" or known["attributes"].get("txt") or self.alias.get(name, name) in self.chain):
                continue                    # the stock page translates this text itself
            if w["kind"] == "t":
                if self.classify(name, w)[0] == "translated":
                    new_text[(name, name)] = self.texts_by_language(name)
            elif w["kind"] == "btn" and len(w["labels"]) == 1 and w["labels"][0].get("centered", True):
                new_text[(name, name)] = {li: (self.label_text(name, li)) for li in range(LANG_COUNT)}
            elif w["kind"] != "t" and len(w["labels"]) == 1 and self.original.get(self.label_name(w)) is None and not (w["kind"] == "key"):
                lname = self.label_name(w)
                new_text[(lname, lname)] = {li: self.label_text(name, li) for li in range(LANG_COUNT)}
        # a static text that has no name in the mockup differs by language when its translations do
        for d in self.decor_texts:
            for li in range(LANG_COUNT):
                match = [x for x in self.spec[0]["languages"][str(li)]["decor"] if x["z"] == d["z"]]
                if match and match[0]["text"].strip() != d["text"].strip():
                    new_text.setdefault((d["name"], d["name"]), {})[li] = match[0]["text"]
        for name, by_language in rules.get("overrides", {}).items():
            for lang, text in by_language.items():
                done = False
                for i, line in enumerate(root.get("codesload", [])):
                    if re.match(r'^\s*%s\.txt=".*"\s*$' % re.escape(name), line) and self.line_language(root["codesload"], i) == lang:
                        root["codesload"][i] = re.sub(r'="(.*)"', lambda m: '="%s"' % esc(text), line)
                        done = True
                if not done:
                    raise ValueError("%s: no text of %s for language %d to override" % (self.old, name, lang))
        additions = {}
        for (name, _), texts in new_text.items():
            for li, text in texts.items():
                if text.strip():
                    additions.setdefault(li, []).append('%s.txt="%s"' % (name, esc(text)))
        lines = add_to_chain(root.get("codesload", []), additions)
        lines = ["vis %s,0" % n for n in self.hidden] + lines
        root["codesload"] = [l.replace("\\r\\n", " ").replace("\\r", " ") if ".txt=" in l else l for l in lines]
        present = {o["attributes"]["objname"] for o in self.stock["objects"]}
        renames = {stock: new for new, stock in self.alias.items() if stock in self.original and new in present and stock not in present}
        allowed = [re.compile(r) for r in rules.get("strip_lines", [])]
        allowed += [re.compile(r"(?<![\w.$])%s\.|\b(?:vis|tsw|click|ref)\s+%s\b" % (re.escape(name), re.escape(name))) for name in rules.get("drop", [])]
        for owner, events in [("(page)", root)] + [(o["attributes"]["objname"], o["events"]) for o in self.stock["objects"]]:
            for ev, lines in events.items():
                kept = []
                for line in lines:
                    line = rename_refs(line, renames)
                    for old, label in self.retarget.items():
                        line = re.sub(r"(?<![\w.$])%s\.(txt|pco|pco2)\b" % re.escape(old), label + r".\1", line)
                    bad = {n for n in names_in(line) if n in gone and n not in present and n not in renames}
                    if bad:
                        if any(r.search(line) for r in allowed):
                            self.report.setdefault("stripped", []).append(line.strip())
                            continue
                        raise ValueError("%s: %s.%s names components that the new page lacks (%s): %s" % (self.old, owner, ev, sorted(bad), line))
                    if re.search(r"\.font=\$\{font:", line):
                        continue                   # every text has its own font now
                    if "${picture:" in line:
                        line = self.new_picture(line, owner, ev)
                    kept.append(line)
                events[ev] = kept
        patch = rules.get("patch")
        if patch:
            patch(self)
        patches.explicit_keypad(self)
        patches.title_touches_back(self)


def merge_faces(faces):
    current = gp.load("tools/faces.json")
    for widget, looks in faces.items():
        current.setdefault(widget, {}).update(looks)
    names = set()
    for path in (ROOT / "pages").glob("*.json"):
        names.update(o["attributes"]["objname"] for o in json.loads(path.read_text(encoding="utf-8"))["objects"]
                     if o["type"] in ("button", "text", "picture"))
    pruned = [w for w in current if w not in names]
    for widget in pruned:
        del current[widget]            # a look of a widget that no page has any more
    gp.save("tools/faces.json", current)
    return pruned


def run(pages):
    project = gp.load("project.json")
    gp.add_fonts(project)
    gp.templates()
    tiles = gp.Tiles(project)
    mapping = gp.load("mockup/pages.json")["pages"]
    inverse = {v: k for k, v in mapping.items()}
    status = 0
    all_faces = {}
    for page in pages:
        old = page if page in mapping else inverse[page]
        rules = rules_mod.RULES.get(old, {})
        try:
            migration = Migration(old, project, tiles, rules)
            report = migration.run()
            for widget, looks in migration.faces.items():
                all_faces.setdefault(widget, {}).update(looks)
            print("%-18s kept %2d  new %2d  dropped %s  baked %d" % (old, len(report["kept"]), len(report["new"]), report["dropped"], report["baked"]))
            if report["new"]:
                print("    new:", ", ".join(report["new"]))
        except ValueError as error:
            status = 1
            print("REFUSED", error)
    gp.save("project.json", project)
    pruned = merge_faces(all_faces)
    if pruned:
        print("looks removed (no such widget any more):", ", ".join(pruned))
    import gen_faces
    gen_faces.main()
    return status


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pages", nargs="*")
    ap.add_argument("--family")
    ap.add_argument("--all", action="store_true", help="again every page that this engine made")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        print(json.dumps(gp.load("tools/migrated.json"), indent=1)[:4000])
        return 0
    pages = list(args.pages)
    if args.all:
        pages += [k for k, v in gp.load("tools/migrated.json").items() if v.get("adapter") == "migrate_pages"]
    if args.family:
        pages += rules_mod.FAMILIES[args.family]
    if not pages:
        ap.error("select pages or a family")
    return run(pages)


if __name__ == "__main__":
    sys.exit(main())
