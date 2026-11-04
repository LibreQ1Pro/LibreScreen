#!/usr/bin/env python3
"""Takes the buttons out of the page backgrounds and the sheets: every button is a tile, a small picture of its own.

    python3 tools/tile_pictures.py --report     (what would change)
    python3 tools/tile_pictures.py              (does it; refuses to run twice; run from display_firmware/)

The stock project drew the buttons into the full-screen backgrounds, and the buttons showed a part of another
full-screen sheet (a sheet held the same button once per place it is used, once released and once pressed). Now

* a page background is the background only (panels, headers, labels): the faces of the buttons are erased from it;
* a button (or an indicator that cropped a sheet) shows ``pic`` / ``pic2``, a tile that has just its size; widgets that
  only crop were turned into pictures (``picture``);
* the tiles that the screen's own code or the host switch (``codesload`` ..., librescreen/pages) are named states:
  ``g.port.face(widget, state)`` of the host sends the two pictures; tools/faces.json lists them (tile_spec.py) and
  gen_faces.py writes librescreen/screen/faces.py from it.

A tile is what the old project showed in the rectangle of the widget (tile_core.py), so the pages look as before; the
pixels around rounded corners are transparent. ``tools/tile_check.py`` renders both projects and compares them.
"""
import json
import os
import re
import sys

import tile_core as core
import tile_names
import tile_plan
from pictures import Pictures, ROOT

NONE = 65535

# pictures that no page refers to but the screen needs
KEEP = set()
# widgets the host hides and shows (g.port.vis); the screen's own code is scanned
HOST_HIDES = {
    "filament_pop_2": {"next_btn", "back_btn", "done_btn", "alt_btn"},
    "filament_pop_3": {"next_btn", "back_btn", "done_btn", "alt_btn"},
    "auto_unload": {"load_btn", "ok"},
}


def blank_for_dead(obj):
    """A widget that sits outside the screen shows nothing."""
    a = obj["attributes"]
    a["sta"] = 3
    for attr in ("picc", "picc2", "pic", "pic2"):
        if attr in a:
            a[attr] = NONE


def to_picture(obj, tile):
    """crop_picture -> picture: the same widget, showing the tile."""
    a = obj["attributes"]
    for attr in ("picc", "vvs0", "vvs1"):
        a.pop(attr, None)
    a["pic"] = core.ref(tile)
    obj["type"] = "picture"


def apply_static(plan, names, project):
    """The widgets that crop a sheet show tiles."""
    for (page, widget), entry in plan.static.items():
        obj = project.widget(page, widget)
        a = obj["attributes"]
        if not entry:
            blank_for_dead(obj)
            continue
        normal, pressed = entry["picc"], entry.get("picc2")
        if obj["type"] == "crop_picture":
            to_picture(obj, names[normal])
            continue
        if (page, widget) not in plan.dynamic and normal.startswith("blank_") and pressed.startswith("blank_"):
            a["sta"] = 3
            a["picc"] = a["picc2"] = a["pic"] = a["pic2"] = NONE
            continue
        a["sta"] = 2
        a["pic"] = core.ref(names[normal])
        a["picc"] = NONE
        if obj["type"] == "button":             # (a text has no pressed look)
            a["pic2"] = core.ref(names[pressed])
            a["picc2"] = NONE


def rewrite_code(plan, names, project):
    """``obj.picc=${picture:K}`` in the code of the pages becomes ``obj.pic=${picture:tile}``."""
    done = {(p, w, s): d for p, w, _, _, s, d in plan.script_uses}
    for page in project.pages:
        for _, lines in tile_plan.event_blocks(project.pages[page]):
            for number, line in enumerate(lines):
                def replace(m):
                    widget, attr, op, sheet = m.groups()
                    digest = done[(page, widget, sheet)]
                    return "%s.%s%s${picture:%s}" % (widget, "pic" if attr == "picc" else "pic2", op, names[digest])
                lines[number] = tile_plan.REFERENCE.sub(replace, line)


def hideable(project, page):
    """The widgets of the page that can be hidden while the page is open."""
    found = set(HOST_HIDES.get(page, ()))
    found.update(re.findall(r"\bvis ([A-Za-z0-9_]+),0", json.dumps(project.pages[page])))
    return found


def drop_dead_background_switch(project):
    """pre_heat: ``if(sys2==1){ b[page].pic=unused_32 }`` can never run (nothing sets sys2 to 1)."""
    lines = project.pages["pre_heat"]["root"]["events"]["codesload"]
    for i, line in enumerate(lines):
        if line.strip() == "if(sys2==1)" and "unused_32" in lines[i + 2]:
            del lines[i:i + 4]
            return


# what is under the faces of some buttons when it is not the colour around them: the panel of the d-pad
FILL = {("move", w): (51, 51, 51) for w in ("y_up", "y_down", "x_up", "x_down", "home_btn")}


def clusters(rects):
    """Groups of rectangles that touch each other (a keypad is one group)."""
    groups = []
    for name, (x, y, w, h) in rects.items():
        near = [g for g in groups if any(not (x + w + 2 < gx or gx + gw + 2 < x or y + h + 2 < gy or gy + gh + 2 < y)
                                         for gx, gy, gw, gh in g["rects"])]
        merged = {"names": [name], "rects": [(x, y, w, h)]}
        for g in near:
            groups.remove(g)
            merged["names"] += g["names"]
            merged["rects"] += g["rects"]
        groups.append(merged)
    return groups


def ring_colour(bg, group, taken):
    """The colour that most of the pixels around a group of rectangles have (three pixels wide, not counting other
    widgets)."""
    xs = [r[0] for r in group["rects"]] + [r[0] + r[2] for r in group["rects"]]
    ys = [r[1] for r in group["rects"]] + [r[1] + r[3] for r in group["rects"]]
    count = {}
    for d in (1, 2, 3):
        x0, y0, x1, y1 = min(xs) - d, min(ys) - d, max(xs) + d - 1, max(ys) + d - 1
        for x in range(x0, x1 + 1):
            for y in (y0, y1):
                count_pixel(bg, x, y, taken, count)
        for y in range(y0, y1 + 1):
            for x in (x0, x1):
                count_pixel(bg, x, y, taken, count)
    return max(count, key=count.get) if count else None


def count_pixel(bg, x, y, taken, count):
    if 0 <= x < core.SCREEN[0] and 0 <= y < core.SCREEN[1] and not any(
            rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in taken):
        colour = bg.getpixel((x, y))[:3]
        count[colour] = count.get(colour, 0) + 1


def new_backgrounds(plan, project):
    """The root pictures of the pages without the faces of the buttons: {page: (old key, image)}.

    A face is replaced by what is under it: where some look of the widget is transparent, the colour that look shows
    there; for the rest the colour that is around the button."""
    result = {}
    for page, data in project.pages.items():
        attrs = data["root"]["attributes"]
        old = core.ref_key(attrs.get("pic"))
        if attrs.get("sta") != 2 or not old:
            continue
        image = project.sheet(old).copy()
        bg = project.background(page)
        hidden = hideable(project, page)
        rects = {}
        for (p, widget) in set(plan.static) | plan.dynamic:
            if p == page:
                rect = core.rect_of(project.widget(page, widget))
                if core.inside(rect):
                    rects[widget] = rect
        everything = list(rects.values())
        for group in clusters(rects):
            ring = None
            for widget in group["names"]:
                rect = rects[widget]
                x, y, w, h = rect
                tile, cleared, _ = core.cut(project, page, rect, None)
                if widget in hidden and not core.is_blank(tile):
                    continue        # the button is drawn into the background and has to stay when the widget is hidden
                fill = FILL.get((page, widget))
                if fill is None and len(group["names"]) == 1:
                    fill = cleared
                if fill is None:
                    ring = ring or ring_colour(bg, group, everything)
                    fill = ring
                underlying = {}
                for (p, wd, sheet), raw in plan.raw.items():
                    if p == page and wd == widget:
                        looks = plan.tiles[plan.of[(p, wd, sheet)]]["image"]
                        for px in range(w):
                            for py in range(h):
                                if looks.getpixel((px, py))[3] == 0 and (px, py) not in underlying:
                                    underlying[(px, py)] = raw.getpixel((px, py))[:3]
                for px in range(w):
                    for py in range(h):
                        colour = underlying.get((px, py))
                        if colour is None and tile.getpixel((px, py))[3] != 0 and fill is not None:
                            colour = tuple(fill)
                        if colour is not None:
                            image.putpixel((x + px, y + py), tuple(colour) + (255,))
        result[page] = (old, image)
    return result


def write_faces(plan, names):
    """tools/faces.json: {widget: {state: [released tile, pressed tile or null]}} (Pictures.save writes faces.py)."""
    faces = {}
    for (widget, state), pages in sorted(plan.states.items()):
        looks = {v for v in pages.values()}
        assert len(looks) == 1, "the widget %s has different looks for the state %s on %s" % (widget, state, sorted(pages))
        one, two = looks.pop()
        faces.setdefault(widget, {})[state] = [names[one], names[two] if two else None]
    with open(os.path.join(ROOT, "tools", "faces.json"), "w", encoding="utf-8") as f:
        json.dump(faces, f, indent=1, ensure_ascii=False)
        f.write("\n")


def referenced(project):
    """Keys of the pictures that a page refers to."""
    pattern = re.compile(r"picture:([A-Za-z0-9_]+)")
    return {key for data in project.pages.values() for key in pattern.findall(json.dumps(data))}


def main():
    project = core.Project()
    plan = tile_plan.Plan(project)
    pics = Pictures()
    names = tile_names.assign(plan, set(pics.keys()))
    if "--report" in sys.argv:
        print("%d tiles for %d widgets, %d looks switched while running" % (len(plan.tiles), len(plan.static), len(plan.states)))
        for problem in sorted(set(plan.problems)):
            print("off the screen:", problem)
        return
    if not plan.static:
        sys.exit("nothing crops a sheet any more: already done")

    for digest, tile in plan.tiles.items():
        path = os.path.join(ROOT, "pictures", names[digest] + ".png")
        tile["image"].save(path)
        pics.add(names[digest], path)
    backgrounds = new_backgrounds(plan, project)
    apply_static(plan, names, project)
    rewrite_code(plan, names, project)
    drop_dead_background_switch(project)
    groups = {}
    for page, (old, image) in backgrounds.items():
        groups.setdefault(old, {}).setdefault(core.digest(image), []).append(page)
    for old, variants in groups.items():
        ordered = sorted(variants.items(), key=lambda kv: -len(kv[1]))
        for n, (_, pages) in enumerate(ordered):
            key = old if n == 0 else "%s_%s" % (old, pages[0])
            path = os.path.join(ROOT, "pictures", key + ".png")
            backgrounds[pages[0]][1].save(path)
            if key not in pics.keys():
                pics.add(key, path)
            for page in pages:
                project.pages[page]["root"]["attributes"]["pic"] = core.ref(key)
    for page in project.pages:
        project.save_page(page)

    # the sheets nobody shows any more
    still = referenced(project)
    host = {names[d] for looks in plan.states.values() for pair in looks.values() for d in pair if d}
    gone = [k for k in pics.keys() if k not in still and k not in KEEP and k not in host]
    pics.project["pictures"] = [p for p in pics.project["pictures"] if p["key"] not in gone]
    for key in gone:
        path = os.path.join(ROOT, "pictures", key + ".png")
        if os.path.exists(path):
            os.remove(path)
    write_faces(plan, names)
    pics.save()
    print("%d tiles, %d pictures removed, %d pictures now" % (len(plan.tiles), len(gone), len(pics.keys())))


if __name__ == "__main__":
    main()
