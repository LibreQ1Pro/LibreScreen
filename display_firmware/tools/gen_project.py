#!/usr/bin/env python3
"""Generate the passive pages of the new design from mockup/layout.json.

    python3 tools/gen_project.py restart_needed shutting_down boot_logo
    python3 tools/gen_project.py --list

Interactive pages require a behaviour adapter (tools/migrate_home.py is the first). Unsupported widgets,
variants and removals are errors, never a reason to drop event code. Source pages are saved once under
migration_sources/; migrated.json records output hashes so a regeneration cannot overwrite hand edits.
The pages are written under their readable names and in the order of the flow (tools/page_names.py); the source names stay the stock ones.
"""
import argparse
import copy
import glob
import hashlib
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

import page_names
import wrap_static

ROOT = Path(__file__).resolve().parent.parent
MOCK = ROOT / "mockup"
TEMPLATE = {}
PASSIVE = {"logo", "restart", "shutdown"}


def rgb565(c):
    """The nearest colour of the screen (5, 6, 5 bits): a colour of the palette is exact, so it is the same whichever way the editor rounds."""
    return (round(c[0] * 31 / 255) << 11) | (round(c[1] * 63 / 255) << 5) | round(c[2] * 31 / 255)


def quantize(image):
    """Tiles and solid component backgrounds must agree at RGB565 precision: every channel goes to the nearest of the 32 / 64 levels (not down), and back to 8 bits
    the way the screen shows it (the top bits repeated)."""
    r, g, b = image.convert("RGB").split()
    r = r.point(lambda v: ((round(v * 31 / 255) << 3) | (round(v * 31 / 255) >> 2)))
    g = g.point(lambda v: ((round(v * 63 / 255) << 2) | (round(v * 63 / 255) >> 4)))
    b = b.point(lambda v: ((round(v * 31 / 255) << 3) | (round(v * 31 / 255) >> 2)))
    return Image.merge("RGB", (r, g, b))


def round_tile(image, mask):
    """A tile with the transparent corners of the HTML (RGBA): ``mask`` is the alpha of the button as the browser draws it (``screenshot(..., layer=True)``). What lies under
    the corners on the page shows through. The pixels of the edge hold the colour of the tile (taken from the nearest solid pixel), not the colour under the corner
    of the mockup: the screen blends them with what is on the page, so a mixed colour would be mixed twice."""
    if mask is None:
        return image
    out = image.convert("RGBA")
    w, h = out.size
    px, mp = out.load(), mask.load()
    cx, cy = (w - 1) / 2, (h - 1) / 2
    for y in range(h):
        for x in range(w):
            if mp[x, y] < 255:
                sx, sy = (1 if x < cx else -1), (1 if y < cy else -1)
                u, v = x, y
                for _ in range(32):
                    if mp[u, v] == 255 or not (0 <= u + sx < w and 0 <= v + sy < h):
                        break
                    u, v = u + sx, v + sy
                px[x, y] = px[u, v][:3] + (0,)
    out.putalpha(mask)
    return out


def to_alpha(image, mode="ink"):
    """An icon cut out of its card as a PNG with alpha: ``ink`` = one colour on a flat background (the ink is the colour farthest from the background, the alpha is
    how far each pixel is on the way to it); ``disc`` = a round badge (the pixels keep their colour, the alpha is the disc, anti-aliased)."""
    from collections import Counter
    rgb = image.convert("RGB")
    w, h = rgb.size
    if mode == "disc":
        scale = 8
        big = Image.new("L", (w * scale, h * scale), 0)
        ImageDraw.Draw(big).ellipse((0, 0, w * scale - 1, h * scale - 1), fill=255)
        out = quantize(rgb).convert("RGBA")
        out.putalpha(big.resize((w, h), Image.BOX))
        return out
    pixels = list(rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata())
    background = Counter(pixels).most_common(1)[0][0]
    ink = max(pixels, key=lambda p: sum((a - b) ** 2 for a, b in zip(p, background)))
    delta = [a - b for a, b in zip(ink, background)]
    norm = sum(d * d for d in delta)
    out = Image.new("RGBA", rgb.size)
    ink = tuple(quantize(Image.new("RGB", (1, 1), ink)).getpixel((0, 0)))
    if norm < 12 * 12:
        out.putdata([ink + (0,)] * len(pixels))
        return out
    alphas = [max(0, min(1, sum((a - b) * d for a, b, d in zip(p, background, delta)) / norm)) for p in pixels]
    out.putdata([ink + (round(a * 255),) for a in alphas])
    return out


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def save(path, data):
    if path.startswith("pages/"):                       # a page: the readable names of the pages in its code, its own name
        data = page_names.rename_refs(data)
        data["name"] = path[len("pages/"):-len(".json")]
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2 if path == "project.json" else 1) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def source_page(old):
    """Reject edits to a generated page; rebuild from its saved source, not the last output."""
    dest = page_names.page_file(old)
    sources = ROOT / "tools/migration_sources"
    source = sources / (old + ".json")
    done = load("tools/migrated.json") if (ROOT / "tools/migrated.json").exists() else {}
    expected = done.get(old, {}).get("sha256")
    if expected and digest(dest) != expected:
        raise ValueError(dest + " was edited after generation; port the change to its adapter first")
    if source.exists():
        return json.loads(source.read_text(encoding="utf-8"))
    sources.mkdir(exist_ok=True)
    source.write_bytes((ROOT / dest).read_bytes())
    return load(dest)


def record(old, report):
    done = load("tools/migrated.json") if (ROOT / "tools/migrated.json").exists() else {}
    done[old] = {**report, "sha256": digest(page_names.page_file(old))}
    save("tools/migrated.json", done)


class Tiles:
    """Opaque (or RGBA) RGB565 tiles. A picture is made once: the same pixels (and size) under any name are the one picture that was made first.
    The key of a picture is ``PAGE_WIDGET`` (``settings_lang_btn``, ``file_list_file1_press``): ``page`` is the page that is being made."""
    page = ""

    def __init__(self, project):
        self.project = project
        self.known = {p["key"] for p in project["pictures"]}
        self.by_pixels = {}
        for key in sorted(self.known):
            path = ROOT / "pictures" / (key + ".png")
            if key != "boot_logo" and path.exists():
                with Image.open(path) as previous:
                    self.by_pixels.setdefault(self.pixels(previous if previous.mode == "RGBA" else previous.convert("RGB")), key)

    @staticmethod
    def pixels(image):
        return "%dx%d:%s" % (image.size[0], image.size[1], hashlib.sha256(image.tobytes()).hexdigest())

    def add(self, name, image):
        alpha = image.getchannel("A") if image.mode == "RGBA" else None
        image = quantize(image)
        if alpha is not None:
            image = image.convert("RGBA")
            image.putalpha(alpha)
        pixels = self.pixels(image)
        if pixels in self.by_pixels:
            key = self.by_pixels[pixels]
            if key not in self.known:
                self.project["pictures"].append({"key": key, "source": {"png": "pictures/%s.png" % key}})
                self.known.add(key)
            return key
        key = name if not self.page or name.startswith(self.page) else "%s_%s" % (self.page, name)
        path = ROOT / "pictures" / (key + ".png")
        if key in self.known:
            # the name is taken by the old look of this widget (the names have the page in them): the new look replaces it under the same name
            for stale in [p for p, k in self.by_pixels.items() if k == key]:
                del self.by_pixels[stale]
            print("picture %s: new look" % key)
        image.save(path)
        if key not in self.known:
            self.project["pictures"].append({"key": key, "source": {"png": "pictures/%s.png" % key}})
            self.known.add(key)
        self.by_pixels[pixels] = key
        return key

    def crop(self, name, rect, image):
        return self.add(name, image.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])))


def screenshot(sid, variant="", lang=2, static=True, nobtn=False, layer=False, names=(), hide=(), hidebox=()):
    """The static rendering of a screen of the mockup (RGB, quantized to RGB565). ``layer=True``: only the buttons, on a transparent background (RGBA, as the browser
    draws it): the alpha of the anti-aliased corners comes from the HTML itself; ``names`` = widgets of the page that belong to the layer besides the buttons; ``hide`` = widgets that are left out of the rendering (components of their own), ``hidebox`` = rectangles (x, y, w, h) whose contents are left out
    (pictures of their own on the page: an icon on a card, the bar of the steps)."""
    directory = ROOT / "out/static"
    directory.mkdir(parents=True, exist_ok=True)
    tag = "_layer" + (("_" + hashlib.sha1(",".join(sorted(names)).encode()).hexdigest()[:8]) if names else "") if layer else ""
    if hide or hidebox:
        tag += "_hide_" + hashlib.sha1((",".join(sorted(hide)) + repr(sorted(hidebox))).encode()).hexdigest()[:8]
    out = directory / ("gen_%s_%s_%d%s%s.png" % (sid, variant, lang, "_nobtn" if nobtn else "", tag))
    query = "bare=%s&lang=%d" % (sid, lang)
    if static:
        query += "&static=1"
    if nobtn:
        query += "&nobtn=1"
    if hide:
        query += "&hide=" + ",".join(sorted(hide))
    if hidebox:
        query += "&hidebox=" + ";".join(",".join(str(v) for v in box) for box in sorted(hidebox))
    if layer:
        query += "&onlybtn=1"
        if names:
            query += "&lyr=" + ",".join(sorted(names))
    if variant:
        query += "&variant=" + variant
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                    "--force-device-scale-factor=1", "--window-size=272,480", "--virtual-time-budget=3000",
                    "--screenshot=" + str(out), (MOCK / "index.html").as_uri() + "?" + query],
                   capture_output=True, timeout=120, check=True)
    with Image.open(out) as image:
        if image.size != (272, 480):
            raise ValueError("unexpected screenshot size: %s" % (image.size,))
        return image.convert("RGBA") if layer else quantize(image)


def templates():
    for path in sorted(glob.glob(str(ROOT / "pages/*.json"))):
        with open(path, encoding="utf-8") as f:
            for obj in json.load(f)["objects"]:
                TEMPLATE.setdefault(obj["type"], obj["attributes"])


def component(kind, name, x=0, y=0, w=0, h=0, **attrs):
    if not name.isascii() or len(name) > 14:
        raise ValueError("invalid component name: " + name)
    a = copy.deepcopy(TEMPLATE[kind])
    a.update({"objname": name, "x": x, "y": y, "w": w, "h": h, "vscope": 0})
    a.update(attrs)
    return {"key": name, "type": kind, "attributes": a, "events": {"codesdown": [], "codesup": []}}


def variable(name, **attrs):
    """A variable of a page (no rectangle)."""
    a = copy.deepcopy(TEMPLATE["variable"])
    a.update({"objname": name})
    a.update(attrs)
    return {"key": name, "type": "variable", "attributes": a, "events": {"codesdown": [], "codesup": []}}


def pic_ref(key):
    return {"$ref": "picture:" + key}


def text_component(widget, name, text=None):
    return component("text", name, widget["x"], widget["y"], widget["w"], widget["h"],
                     sta=3, style=0, key=255, borderw=0, bco=rgb565(widget["matte"]), pco=rgb565(widget["color"]),
                     font={"$ref": "font:font_" + widget["role"]},
                     xcen={"l": 0, "c": 1, "r": 2}[widget["align"]], ycen=0 if widget.get("top") else 1,
                     picc=65535, pic=65535, txt=widget.get("text", "") if text is None else text,
                     txt_maxl=1024 if widget.get("dyn") else 512, isbr=1, spax=0, spay=0)


def unbreak(lines):
    """Remove old hand wrapping from string assignments only; NEVER remove executable lines."""
    return [line.replace("\\r\\n", " ").replace("\\r", " ") if ".txt=" in line else line for line in lines]


def wrap_fixed_texts(lines, texts):
    """The fixed texts (``name.txt="..."``) of a passive page with the line breaks at the ends of the words (tools/wrap_static.py)."""
    result = []
    for line in lines:
        match = re.match(r'^(\s*)(\w+)\.txt="((?:[^"\\]|\\.)*)"$', line)
        widget = texts.get(match.group(2)) if match else None
        if widget is None or widget.get("dyn"):
            result.append(line)
            continue
        wrapped, _ = wrap_static.wrap(match.group(3), widget["role"], widget["w"] - 4)
        result.append('%s%s.txt="%s"' % (match.group(1), match.group(2), wrapped))
    return result


def add_fonts(project):
    have = {font["key"] for font in project["fonts"]}
    for role in ("t13", "t16", "t19", "d20", "d28", "d32"):
        if not (ROOT / "fonts" / ("font_%s.zi" % role)).exists():
            raise ValueError("run tools/make_fonts.py first")
        if "font_" + role not in have:
            project["fonts"].append({"key": "font_" + role, "source": {"zi": "fonts/font_%s.zi" % role}})


def generate(old, scr, project, tiles):
    stock = source_page(old)
    original = {obj["attributes"]["objname"]: obj for obj in stock["objects"]}
    texts = {widget["name"]: widget for widget in scr["widgets"] if widget["kind"] == "t"}
    invisible = {name for name, obj in original.items() if obj["type"] in ("timer", "variable", "touch_capture")}
    gone = set(original) - set(texts) - invisible - {name for name in original if name.startswith(("ico", "bg"))}
    if gone:
        raise ValueError("%s requires a behaviour adapter: missing %s" % (old, sorted(gone)))
    shot = screenshot(scr["id"], scr["variant"])
    objects = [copy.deepcopy(original[name]) for name in original if name in invisible]
    # the boot logo is the picture of the project (the mockup only marks its place with a box)
    for prim in ([] if old == "logo" else scr["prims"]):
        key = tiles.crop("static", prim, shot)
        objects.append(component("picture", "bg%d" % prim["z"], prim["x"], prim["y"], prim["w"], prim["h"], pic=pic_ref(key)))
    for name, widget in texts.items():
        comp = text_component(widget, name)
        if not widget.get("dyn"):
            comp["attributes"]["txt"], _ = wrap_static.wrap(comp["attributes"]["txt"], widget["role"], widget["w"] - 4)
        if old == "logo":
            comp["attributes"].update(sta=3)             # over the picture of the logo
        if name in original:
            comp["events"] = copy.deepcopy(original[name]["events"])
        objects.append(comp)
    stock["objects"] = objects
    if old != "logo":
        stock["root"]["attributes"].update(sta=1, bco=rgb565(scr["bg"]), pic=65535)
    for event, lines in stock["root"]["events"].items():
        stock["root"]["events"][event] = wrap_fixed_texts(unbreak(lines), texts)
    save(page_names.page_file(old), stock)
    record(old, {"design": scr["page"], "adapter": "passive", "kept": sorted(set(texts) & set(original)), "new": sorted(set(texts) - set(original))})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pages", nargs="*")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print(json.dumps(load("tools/migrated.json"), indent=1))
        return
    if not args.pages:
        ap.error("select pages explicitly")
    mapping = load("mockup/pages.json")["pages"]
    inverse = {v: k for k, v in mapping.items()}
    layout = load("mockup/layout.json")
    selected = []
    for arg in args.pages:
        old = arg if arg in mapping else inverse.get(arg)
        if old not in PASSIVE:
            ap.error("%s requires a behaviour adapter (not a passive page)" % arg)
        screens = [s for s in layout if s["old"] == old]
        if len(screens) != 1 or any(w["kind"] != "t" for w in screens[0]["widgets"]):
            ap.error("%s has unsupported widgets or variants" % arg)
        selected.append((old, screens[0]))
    project = load("project.json")
    add_fonts(project)
    templates()
    tiles = Tiles(project)
    for old, scr in selected:
        generate(old, scr, project, tiles)
        print(old + " -> design " + scr["page"] + " (behaviour retained)")
    save("project.json", project)


if __name__ == "__main__":
    main()
