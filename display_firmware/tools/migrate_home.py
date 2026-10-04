#!/usr/bin/env python3
"""Port the Home design and its screen-side behaviour, without changing page/action numbers.

    python3 tools/migrate_home.py

Temperatures become text fields (--- until the host sets them); their targets/units are separate.
Heater icons change independently of the text so a face update cannot erase a cached temperature.
Touch hotspots cover the full heater cards. Buttons and navigation retain their original UART actions;
all pictures are opaque RGB565 tiles, including pressed states. The version warning and sleep logic stay.
"""
import copy
import json

from PIL import Image

import gen_faces
import page_names
from gen_project import (ROOT, Tiles, add_fonts, component, load, pic_ref, quantize, record, round_tile, to_alpha,
                         rgb565, save, screenshot, source_page, templates, text_component, unbreak)

TEXT = (247, 247, 247)
MUTED = (165, 166, 181)
HOT = (255, 121, 90)
PANEL = (41, 40, 41)


TOGGLE = {"nozzle": 7, "bed": 8, "chamber": 9}         # librescreen/screen/pageids.py MAIN_TOGGLE_*


def slashed(image, ink, background):
    """The icon crossed out (the network or the drive is not there): a diagonal line with a gap of the background on each side of it."""
    from PIL import ImageDraw
    scale = 4
    big = image.resize((image.width * scale, image.height * scale), Image.LANCZOS)
    draw = ImageDraw.Draw(big)
    a, b = (2 * scale, 2 * scale), ((image.width - 2) * scale, (image.height - 2) * scale)
    draw.line([a, b], fill=tuple(background), width=5 * scale)
    draw.line([a, b], fill=tuple(ink), width=2 * scale)
    return quantize(big.resize(image.size, Image.LANCZOS))


def recolor(image, old, new, background, new_background=None):
    """Recolour the anti-aliased ink of one icon; its matte stays unchanged."""
    old, new, background = [quantize(Image.new("RGB", (1, 1), tuple(c))).getpixel((0, 0)) for c in (old, new, background)]
    new_background = background if new_background is None else quantize(Image.new("RGB", (1, 1), new_background)).getpixel((0, 0))
    delta = [a - b for a, b in zip(old, background)]
    norm = sum(v * v for v in delta)
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    result = []
    for pixel in pixels:
        alpha = max(0, min(1, sum((a - b) * d for a, b, d in zip(pixel, background, delta)) / norm))
        result.append(tuple(round(b + alpha * (n - b)) for b, n in zip(new_background, new)))
    out = Image.new("RGB", image.size)
    out.putdata(result)
    return quantize(out)


def crop(image, rect):
    return image.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]))


def main():
    project = load("project.json")
    add_fonts(project)
    templates()
    stock = source_page("main")
    old = {obj["attributes"]["objname"]: obj for obj in stock["objects"]}
    screens = [s for s in load("mockup/layout.json") if s["old"] == "main"]
    normal = next(s for s in screens if s["variant"] == "normal")
    cold = next(s for s in screens if s["variant"] == "no_values")
    warning = next(s for s in screens if s["variant"] == "ver_warning")
    widgets = {w["name"]: w for w in normal["widgets"]}
    warn_widgets = {w["name"]: w for w in warning["widgets"]}
    tiles, faces = Tiles(project), load("tools/faces.json")
    tiles.page = "home"
    shot = screenshot("home", "no_values")
    full = screenshot("home", "normal", static=False)
    objects = [copy.deepcopy(obj) for obj in stock["objects"] if obj["type"] in ("timer", "touch_capture")]
    handled = set()

    def picture(name, rect, image):
        key = tiles.add(name, image)
        obj = component("picture", name, rect["x"], rect["y"], rect["w"], rect["h"], pic=pic_ref(key))
        objects.append(obj)
        return obj

    layer = screenshot("home", "no_values", layer=True, names=[w["name"] for w in normal["widgets"] if w["name"]])

    def mask_of(name):
        """The alpha of a button as the browser draws it (the layer of the buttons of the mockup), None for a button without a fill of its own."""
        fill = next((p for p in normal["prims"] if p["prim"] == "fill" and (p.get("name") == name or p.get("owner") == name)), None)
        if fill is None:
            return None
        rect = {k: fill[k] for k in ("x", "y", "w", "h")}
        mask = layer.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])).getchannel("A")
        return mask if mask.getpixel((rect["w"] // 2, rect["h"] // 2)) == 255 else None

    def button(name, rect, released, pressed):
        mask = mask_of(name)                           # the tiles have transparent rounded corners (alpha), like the buttons of the other pages
        key = tiles.add(name, round_tile(released, mask))
        key2 = tiles.add(name + "_press", round_tile(pressed, mask))
        obj = component("button", name, rect["x"], rect["y"], rect["w"], rect["h"], sta=2, style=0, borderw=0,
                        font={"$ref": "font:font_t16"}, pic=pic_ref(key), pic2=pic_ref(key2), picc=65535, picc2=65535,
                        txt="", txt_maxl=1, pco=rgb565(TEXT), pco2=rgb565(TEXT))
        obj["events"] = copy.deepcopy(old[name]["events"])
        objects.append(obj)
        handled.add(name)
        return key, key2

    # Network/USB indicators are not touch targets, and their state does not affect any other widget.
    for glyph, name in (("ethernet-port", "lan_icon"), ("usb", "usb_icon"), ("wifi", "wifi_icon")):
        prim = next(p for p in normal["prims"] if p.get("icon") == glyph)
        image = crop(shot, prim)
        off = tiles.add(name, slashed(image, MUTED, normal["bg"]))
        on = tiles.add(name + "_on", recolor(image, MUTED, TEXT, normal["bg"]))
        picture(name, prim, slashed(image, MUTED, normal["bg"]))
        faces[name] = {"off": [off, None], "on": [on, None]}
        handled.add(name)

    last = widgets["last_file_btn"]
    image = crop(shot, last)
    pair = button("last_file_btn", last, image, image.point(lambda c: round(c * 0.82)))
    faces["last_file_btn"] = {"photo": list(pair), "noimg": list(pair)}
    thumb = widgets["last_file_pic"]
    picture("thumb_empty", thumb, crop(full, thumb))
    colpic = copy.deepcopy(old["last_file_pic"])
    colpic["attributes"].update({key: thumb[key] for key in ("x", "y", "w", "h")})
    colpic["attributes"].update(vscope=1)
    objects.append(colpic)
    handled.add("last_file_pic")

    for heater in ("nozzle", "bed", "chamber"):
        name = heater + "_btn"
        rect = widgets[name]
        icon = next(p for p in cold["prims"] if p.get("icon") == "heat-" + heater)
        image, ink = crop(shot, rect), crop(shot, icon)
        # The card is static. Only the icon changes at run time, never a tile underneath a text field.
        image.paste(quantize(Image.new("RGB", ink.size, PANEL)), (icon["x"] - rect["x"], icon["y"] - rect["y"]))
        picture(heater + "_card", rect, image)
        icon_name = heater + "_icon"
        off = tiles.add(icon_name, to_alpha(ink))
        on = tiles.add(icon_name + "_on", to_alpha(recolor(ink, MUTED, HOT, PANEL)))
        picture(icon_name, icon, to_alpha(ink))
        faces[icon_name] = {"off": [off, None], "on": [on, None]}
        # Main-specific old looks must not survive with their old geometry; print looks are retained.
        for state in ("on", "off"):
            faces.get(name, {}).pop(state, None)
        # the icon (the left 50 px of the card) switches the heater, the rest opens the keyboard: two hotspots that do not overlap
        hotspot = component("touch_hotspot", name, rect["x"] + 50, rect["y"], rect["w"] - 50, rect["h"])
        hotspot["events"] = copy.deepcopy(old[name]["events"])
        objects.append(hotspot)
        toggle = component("touch_hotspot", heater + "_toggle", rect["x"], rect["y"], 50, rect["h"])
        toggle["events"] = {"codesdown": [], "codesup": ["prints 0x65,1", "prints dp,1", "prints %d,1" % TOGGLE[heater], "prints 0xff,1", "prints 0xff,1", "prints 0xff,1"]}
        objects.append(toggle)
        handled.add(name)

    for name in ("light_btn", "beep_btn", "stop_btn"):
        rect = widgets[name]
        image = crop(shot, rect)
        if name == "light_btn":
            # The mockup shows light on; the off state has the common button fill and a muted icon.
            on = image
            off = crop(shot, widgets["beep_btn"])
            icon = next(p for p in normal["prims"] if p.get("icon") == "lightbulb")
            ink = crop(shot, icon)
            bulb = recolor(ink, (255, 255, 255), MUTED, (57, 121, 255), (49, 48, 57))
            off.paste(bulb, (icon["x"] - rect["x"], icon["y"] - rect["y"]))
        elif name == "beep_btn":
            off = image
            on = recolor(off, (49, 48, 57), (57, 121, 255), normal["bg"])
            icon = next(p for p in normal["prims"] if p.get("icon") == "volume-2")
            on.paste(recolor(crop(shot, icon), MUTED, (255, 255, 255), (49, 48, 57), (57, 121, 255)),
                     (icon["x"] - rect["x"], icon["y"] - rect["y"]))
        else:
            button(name, rect, image, image.point(lambda c: round(c * 0.82)))
            continue
        pair_off = button(name, rect, off, off.point(lambda c: round(c * 0.82)))
        mask = mask_of(name)
        pair_on = [tiles.add(name + "_on", round_tile(on, mask)), tiles.add(name + "_on_press", round_tile(on.point(lambda c: round(c * 0.82)), mask))]
        faces[name]["off"], faces[name]["on"] = list(pair_off), pair_on

    nav = next(p for p in normal["prims"] if p.get("cls") == "nav")
    for name in ("nav_main", "nav_adjust", "nav_files", "nav_settings"):
        rect = dict(widgets[name], y=nav["y"], h=nav["h"])
        image = crop(shot, rect)
        button(name, rect, image, image.point(lambda c: round(c * 0.82)))

    for widget in normal["widgets"]:
        if widget["kind"] != "t":
            continue
        name = widget["name"]
        value = "" if name == "last_file_name" else "/ ---" if name.endswith("_set") else "---" if name.endswith("_temp") else widget["text"]
        field = text_component(widget, name, value)
        if name.endswith("_temp"):
            field["attributes"]["pco"] = rgb565(TEXT)
        if name == "last_file_name":
            field["attributes"]["vscope"] = 1
        if name in old:
            field["events"] = copy.deepcopy(old[name]["events"])
            handled.add(name)
        objects.append(field)

    # Keep the warning separate, on top of the normal page. Host version is numeric in logo.version,
    # but the newly laid-out SOC field is text; conversion happens explicitly in codesload.
    panel = next(p for p in warning["prims"] if p.get("bg") == [12, 12, 14])
    picture("ver_panel", panel, crop(screenshot("home", "ver_warning"), panel))
    for name in ("ver_warning", "ui_ver_lbl", "ui_ver", "soc_ver_lbl", "soc_ver"):
        objects.append(text_component(warn_widgets[name], name, "" if name == "soc_ver" else warn_widgets[name]["text"]))
        handled.add(name)
    missing = set(old) - handled - {obj["attributes"]["objname"] for obj in objects}
    if missing:
        raise ValueError("unhandled source widgets: " + ", ".join(sorted(missing)))
    if len(objects) > 254:
        raise ValueError("component limit exceeded")
    stock["objects"] = objects
    stock["root"]["attributes"].update(sta=1, bco=rgb565(normal["bg"]), pic=65535)
    translations = stock["root"]["events"]["codesload"][8:]
    stock["root"]["events"]["codesload"] = [
        "covx logo.version.val,soc_ver.txt,0,0", "vis last_file_pic,0", "if(logo.version.val==100)", "{",
        *["  vis %s,0" % name for name in ("ver_panel", "ver_warning", "ui_ver_lbl", "ui_ver", "soc_ver_lbl", "soc_ver")],
        "}", *unbreak(translations)]
    save(page_names.page_file("main"), stock)
    save("project.json", project)
    save("tools/faces.json", faces)
    gen_faces.main()
    record("main", {"design": "home", "adapter": "migrate_home.py", "kept": sorted(handled & set(old)),
                    "new": sorted({obj["attributes"]["objname"] for obj in objects} - set(old))})
    print("main -> Home: %d components, original actions retained" % len(objects))


if __name__ == "__main__":
    main()
