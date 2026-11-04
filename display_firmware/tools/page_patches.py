"""Hand adapters of pages whose behaviour the engine (migrate_pages.py) cannot take over from the stock events: the value keyboards.

Every function takes the ``Migration`` (``m.stock`` is the page that is being made) and edits its events.
"""
import json

import page_names
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXTS = json.loads((ROOT / "mockup" / "texts.json").read_text(encoding="utf-8"))
LANGUAGES = 13


def page_number(key):
    """The id of a page: its position in project.json (the host knows it as librescreen/screen/pageids.py)."""
    pages = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))["pages"]
    return [p["key"] for p in pages].index(page_names.new(key))


def esc(text):
    return text.replace("\\", "/").replace('"', "'").replace("\n", " ").strip()


def object_named(m, name):
    return next(o for o in m.stock["objects"] if o["attributes"]["objname"] == name)


def titles_chain(modes_var, modes):
    """The code that sets ``title.txt`` by language and mode: ``modes`` = [(mode number, page of the texts, key of the texts)]."""
    lines = []
    for lang in range(LANGUAGES):
        lines += [("if" if lang == 0 else "}else if") + "(lang==%d)" % lang, "{"]
        for i, (number, page, key) in enumerate(modes):
            texts = TEXTS[page][key]
            lines += [("  if" if i == 0 else "  }else if") + "(%s==%d)" % (modes_var, number), "  {",
                      '    title.txt="%s"' % esc(texts[lang] if lang < len(texts) else texts[2])]
        lines += ["  }"]
    return lines + ["}"]


def value_frame(page_id, var, value_expr, widget_cases):
    """The frame ``71 page widget lo hi`` (a number of two bytes) the keyboards send when the value is accepted."""
    lines = ["prints 113,1", "prints %d,1" % page_id]
    for i, (number, widget) in enumerate(widget_cases):
        lines += [("if" if i == 0 else "}else if") + "(%s==%d)" % (var, number), "{", "  prints %d,1" % widget]
    lines += ["}", "prints %s,2" % value_expr] + ["prints 0xff,1"] * 3
    return lines


# -- the number keyboard of the pages without a print status: nozzle, bed, chamber and the three fans (sys1 0..5)
FILAMENT_KB_MODES = [(0, "°C", 350, "title@sys1=0", "filament_kb", 0), (1, "°C", 120, "title@sys1=1", "filament_kb", 1),
                     (2, "°C", 60, "title@sys1=2", "filament_kb", 16),
                     (3, "%", 100, "title@sys0=4", "keybdB", 12), (4, "%", 100, "title@sys0=5", "keybdB", 13), (5, "%", 100, "title@sys0=6", "keybdB", 14)]


def patch_filament_kb(m):
    root = m.stock["root"]["events"]
    lines = ['input.txt=""', 'input_show.txt=""', "inputlenth.val=3"]
    for i, (mode, unit, limit, *_rest) in enumerate(FILAMENT_KB_MODES):
        lines += [("if" if i == 0 else "}else if") + "(sys1==%d)" % mode, "{", '  input_unit.txt="%s"' % unit, '  input_max.txt="MAX : %d"' % limit]
    lines += ["}"]
    lines += titles_chain("sys1", [(mode, page, key) for mode, _u, _l, key, page, _w in FILAMENT_KB_MODES])
    root["codesload"] = lines
    ok = object_named(m, "key_ok")
    ok["events"]["codesup"] = (["strlen input_show.txt,str_len.val", "covx input_show.txt,txt_to_val.val,str_len.val,0"] +
                               value_frame(page_number("filament"), "sys1", "txt_to_val.val", [(mode, widget) for mode, _u, _l, _k, _p, widget in FILAMENT_KB_MODES]))


# -- the number keyboard of the print pages (sys0: 0 nozzle, 1 bed, 2 speed, 3 flow, 4..6 fans, 7 chamber)
KEYBDB_UNITS = {0: "°C", 1: "°C", 2: "%", 3: "%", 4: "%", 5: "%", 6: "%", 7: "°C"}


def patch_keybdB(m):
    root = m.stock["root"]["events"]
    lines = ["thumb.close()", "thumb.write(preview.cp_data_s.txt)", 'time_elapsed.txt=""', 'time_left.txt=""', 'file_name.txt=""',
             "if(sys0!=2)", "{", "  vis mute_btn,0", "}",
             "if(printing.thumb_flag.val==0)", "{", "  vis thumb,0", "}else", "{", "  vis thumb,1", "}",
             'input.txt=""', 'input_show.txt=""', "inputlenth.val=3"]
    for i, (mode, unit) in enumerate(sorted(KEYBDB_UNITS.items())):
        lines += [("if" if i == 0 else "}else if") + "(sys0==%d)" % mode, "{", '  input_unit.txt="%s"' % unit]
    lines += ["}"]
    lines += titles_chain("sys0", [(mode, "keybdB", "title@sys0=%d" % mode) for mode in sorted(KEYBDB_UNITS)])
    root["codesload"] = lines
    object_named(m, "key_ok")["events"]["codesup"] = (
        ["covx input.txt,temp.val,0,0", "prints 113,1", "prints %d,1" % page_number("printing"), "prints sys0,1", "prints temp.val,2"] + ["prints 0xff,1"] * 3 + ["page loadpageid.val"])


def patch_filelist(m):
    """The thumbnail of a slot is exactly the size of its placeholder (112 x 112, a multiple of 16: the JPEG decoder of the screen shears a picture whose width is not; 4:4:4, the screen shows 4:2:0 in blocks); the card colour
    and the round corners are in the pixels (librescreen/screen/thumbnail.py ``jpeg``)."""
    # until the host says what the slots hold they show nothing (a slot without an entry has no card, the boxes of its name and picture are not drawn)
    hidden = ["vis file%d_%s,0" % (number, part) for number in (1, 2, 3, 4) for part in ("pic_bg", "pic", "name")]
    m.stock["root"]["events"]["codesload"] = hidden + m.stock["root"]["events"].get("codesload", [])


def patch_filament(m):
    """The number of a fan tile is a text on top of the tile: it forwards the touch to the tile (the tile sends the action)."""
    for number in (1, 2, 3):
        object_named(m, "fan%d_val" % number)["events"] = {"codesdown": ["click fan%d_btn,1" % number], "codesup": ["click fan%d_btn,0" % number]}


def patch_printing_2(m):
    """The fan tiles of the second print page open the number keyboard like those of the first page (the screen binds the value to the keyboard, key=2);
    the host gets the action that says so (5, 6, 7) and the keyboard answers with ``71 20 <fan> <value>`` as for the first page."""
    for number, (mode, action) in enumerate(((4, 5), (5, 6), (6, 7)), 1):
        card, value = object_named(m, "fan%d_btn" % number), object_named(m, "fan%d_val" % number)
        card["events"] = {"codesdown": [], "codesup": ["click fan%d_val,0" % number]}
        value["attributes"]["key"] = 2
        value["events"] = {"codesdown": ["click fan%d_btn,1" % number],
                           "codesup": ["sys0=%d" % mode, "prints 0x65,1", "prints dp,1", "prints %d,1" % action] + ["prints 0xff,1"] * 3}


def explicit_keypad(m):
    """A value of a print page that opens the number keyboard does it by itself: the stock binds it to the system keyboard page (``key=2``: the editor fixes the
    name of that page and the screen opens it without the program saying so). Here the touch says where to return (``loadpageid`` of the keyboard) and opens the page."""
    keypad = page_names.new("keybdB")
    for obj in m.stock["objects"]:
        if obj["attributes"].get("key", 255) != 2:
            continue
        obj["attributes"]["key"] = 255
        up = obj["events"]["codesup"]
        first = next(i for i, line in enumerate(up) if line.strip() == "prints 0x65,1")      # (a line may be inside an ``if``: keep its indent)
        last = max(i for i, line in enumerate(up) if line.strip() == "prints 0xff,1")
        indent = lambda i: up[i][:len(up[i]) - len(up[i].lstrip())]
        up[last + 1:last + 1] = [indent(last) + "page %s" % keypad]
        up[first:first] = [indent(first) + "%s.loadpageid.val=dp" % keypad]


def title_touches_back(m):
    """A touch on the title of a header goes to the back button (the title lies over it and takes the touch): the header is lit as a whole and goes back."""
    objects = {o["attributes"]["objname"]: o for o in m.stock["objects"]}
    back, title = objects.get("back_btn"), objects.get("title")
    if back and title and title["type"] == "text" and not title["events"].get("codesdown") and not title["events"].get("codesup"):
        title["events"]["codesdown"] = ["click back_btn,1"]
        title["events"]["codesup"] = ["click back_btn,0"]


def patch_preview(m):
    """``cp_data_s`` holds the ColPic of the thumbnail for the number keyboard of the print pages (72 x 72), like ``cp_data`` does for the print pages (132 x 132);
    it is a hidden text beside ``cp_data`` (the pages of a print write them into their ``thumb``)."""
    import copy
    base = object_named(m, "cp_data")
    extra = copy.deepcopy(base)
    extra["key"] = "cp_data_s"
    extra["attributes"]["objname"] = "cp_data_s"
    extra["attributes"]["y"] = base["attributes"]["y"] + 60
    m.stock["objects"].append(extra)
    for name in ("est_time", "fil_length", "fil_type", "fil_weight"):       # the details of the file are not known until the host has read them
        object_named(m, name)["attributes"]["txt"] = "---"


# -- the Wi-Fi keyboard: ``kmode`` is the page of keys (0 lower case, 1 upper case, 2 and 3 the pages of symbols)
def patch_wifi_kb(m):
    from gen_project import variable
    m.stock["objects"].append(variable("kmode", sta=0, val=0))
    # the shift key shows "1/2" and "2/2" on the pages of symbols: its text holds four characters (the key has an icon on the letter pages, so no label gave it room)
    sym = object_named(m, "key_sym")["attributes"]
    object_named(m, "key_shift")["attributes"].update(txt_maxl=4, font=sym["font"], pco=sym["pco"], pco2=sym["pco2"], isbr=0)
    look = m.looks["key_shift"]
    pics = {state: ("${picture:%s}" % look[state][0], "${picture:%s}" % look[state][1]) for state in look}

    def show(state):
        return ["key_shift.pic=" + pics[state][0], "key_shift.pic2=" + pics[state][1]]

    object_named(m, "key_shift")["events"]["codesup"] = (
        ["if(kmode.val==0)", "{", "  kmode.val=1"] + ["  " + l for l in show("upper")] +
        ["}else if(kmode.val==1)", "{", "  kmode.val=0"] + ["  " + l for l in show("lower")] +
        ["}else if(kmode.val==2)", "{", "  kmode.val=3", '  key_shift.txt="2/2"',
         "}else", "{", "  kmode.val=2", '  key_shift.txt="1/2"', "}", "click refresh_show,0"])
    object_named(m, "key_sym")["events"]["codesup"] = (
        ["if(kmode.val<2)", "{", "  kmode.val=2", '  key_sym.txt="abc"'] + ["  " + l for l in show("sym")] + ['  key_shift.txt="1/2"'] +
        ["}else", "{", "  kmode.val=0", '  key_sym.txt="123"'] + ["  " + l for l in show("lower")] + ['  key_shift.txt=""', "}", "click refresh_show,0"])
    refresh = object_named(m, "refresh_show")["events"]["codesup"]
    for old, new in (("if(key_shift.pic==", "if(kmode.val==0)"), ("}else if(key_shift.pic==", "}else if(kmode.val==1)"),
                     ('}else if(key_shift.txt=="1/2")', "}else if(kmode.val==2)"), ('}else if(key_shift.txt=="2/2")', "}else if(kmode.val==3)")):
        for i, line in enumerate(refresh):
            if line.startswith(old) or line == old:
                refresh[i] = new


def patch_move(m):
    """Until the host says where the axes are (or while an axis is not homed), the positions show ``---.-``."""
    for name in ("x_pos", "y_pos", "z_pos"):
        object_named(m, name)["attributes"]["txt"] = "---.-"


def patch_sleep_mode(m):
    """The brightness value next to the slider follows it (``covx`` turns the number into text).
    A time option is applied on the spot: the page stays, only the chosen option is lit (the others get their normal look back)."""
    import re
    root = m.stock["root"]["events"]
    on_pic, on_pic2 = re.findall(r"opt_5min\.pic2?=(\$\{picture:[^}]+\})", "\n".join(root["codesload"]))[:2]
    any_option = object_named(m, "opt_5min")["attributes"]
    off_pic, off_pic2 = ("${picture:%s}" % any_option[k]["$ref"].split(":", 1)[1] for k in ("pic", "pic2"))
    options = {"opt_5min": 300, "opt_15min": 900, "opt_30min": 1800, "opt_never": 0}
    for name, seconds in options.items():
        code = ["sleep_time=%d" % seconds, "wepo sleep_time,200"]
        for other in options:
            code += ["%s.pic=%s" % (other, on_pic if other == name else off_pic), "%s.pic2=%s" % (other, on_pic2 if other == name else off_pic2)]
        object_named(m, name)["events"]["codesup"] = code
    root["codesload"].append("covx bright_slider.val,bright_val.txt,0,0")
    slider = object_named(m, "bright_slider")
    slider["events"]["codesslide"].append("covx bright_slider.val,bright_val.txt,0,0")
