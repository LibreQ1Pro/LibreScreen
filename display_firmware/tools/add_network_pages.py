#!/usr/bin/env python3
"""NOTE: written against the stock names (b0, t1, pic_25 ...); the components and pictures were renamed afterwards
(tools/names.json maps the stock names to the final ones), so this script only documents how the pages were made.

Adds the NetworkManager pages to the screen project (run from display_firmware/ once, on the stock V4.4.24 sources).

New pages (appended, so the ids of the old ones do not change):
  110 net_saved    list of the saved Wi-Fi connections (like wifi_list, 5 rows, paging)
  111 net_detail   one saved connection: connect / disconnect, change password, autoconnect, forget
  112 net_confirm  "forget the network?"
  113 net_info     the state of the Wi-Fi and LAN interfaces, Wi-Fi radio switch
Changed pages:
  wifi_list (51)   the IP box became the buttons "Saved" and "Hidden"
  wifi_kb (56)     the keyboard works in several modes: it sends ``0x70 kbmode row text``, the text is
                   accepted from ``kbmin`` characters (the host sets both before opening the page)
  internet_page (81) the dead QIDI Link rows became "Network info", "Saved networks", "Hidden network"
Global variables added to Program.s: kbmode, kbmin.

Protocol (display -> host) of the new pages: ``0x65 <page id> <action> ff ff ff``, see ACTIONS below.
"""
import copy
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

PANEL = (38, 38, 38)
BAR = (102, 102, 102)
BAR_PRESSED = (136, 136, 136)
RED = (150, 56, 56)
RED_PRESSED = (190, 84, 84)
BOX = (112, 112, 112)
WHITE = 65535
GREY565 = 0x94B2        # (150,150,150)
END = ["prints 0xff,1", "prints 0xff,1", "prints 0xff,1"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def rgb565(c):
    return ((c[0] >> 3) << 11) | ((c[1] >> 2) << 5) | (c[2] >> 3)


# ---------------------------------------------------------------------------------------------- pictures
from draw_network_pictures import draw_all as make_pictures      # noqa: E402  (tools/ is on the path of this script)


# ---------------------------------------------------------------------------------------------- components
WL = load("pages/wifi_list.json")
T = {o["key"]: o for o in WL["objects"]}


def ref(kind, key):
    return {"$ref": "%s:%s" % (kind, key)}


def action(n, extra=()):
    return list(extra) + ["prints 0x65,1", "prints dp,1", "prints %d,1" % n] + END


def button(key, x, y, w, h, txt, n, bg, pressed, pco=WHITE, maxl=40, extra=()):
    o = copy.deepcopy(T["wifi1"])
    o["key"] = key
    a = o["attributes"]
    a.update(objname=key, x=x, y=y, w=w, h=h, txt=txt, txt_maxl=maxl, pco=pco, pco2=pco,
             picc=ref("picture", bg), picc2=ref("picture", pressed))
    o["events"] = {"codesdown": [], "codesup": action(n, extra)}
    return o


def text(key, x, y, w, h, txt="", maxl=60, xcen=0, ycen=1, wrap=1, pco=WHITE):
    o = copy.deepcopy(T["t1"])
    o["key"] = key
    o["attributes"].update(objname=key, x=x, y=y, w=w, h=h, txt=txt, txt_maxl=maxl, xcen=xcen, ycen=ycen,
                           isbr=wrap, pco=pco)
    o["events"] = {"codesdown": [], "codesup": []}
    return o


def common(title_en):
    """Back button, title, navigation bar, touch capture and the screen saver timer (as on wifi_list)."""
    objs = [copy.deepcopy(T[k]) for k in ("b23", "t6", "b30", "b31", "b32", "b33", "touch", "sleep_counter")]
    objs[1]["attributes"]["txt"] = title_en
    return objs


def i18n(strings):
    """codesload lines: strings = {"obj.attr": (english, russian)} - Russian for lang 1, English for the rest."""
    lines = ["if(lang==1)", "{"]
    lines += ['  %s="%s"' % (k, v[1]) for k, v in strings.items()]
    lines += ["}else", "{"]
    lines += ['  %s="%s"' % (k, v[0]) for k, v in strings.items()]
    lines += ["}"]
    return lines


def page(title_key, bg, objects, load_lines):
    p = copy.deepcopy(WL)
    p["name"] = title_key
    p["root"]["attributes"]["pic"] = ref("picture", bg)
    p["root"]["events"]["codesload"] = load_lines
    p["objects"] = objects
    return p


# ---------------------------------------------------------------------------------------------- the pages
def build_pages():
    pages = {}

    # net_saved: wifi_list without the IP box / refresh
    rows = [copy.deepcopy(T[k]) for k in ("wifi1", "wifi2", "wifi3", "wifi4", "wifi5", "t1", "t2", "t3", "t4", "t5",
                                           "b1", "b2")]
    objs = common("Saved networks") + rows
    pages["net_saved"] = page("net_saved", "net_bg_blank", objs, i18n({"t6.txt": ("Saved networks", "Сохранённые сети")}))

    # net_detail
    objs = common("Network") + [
        text("tssid", 28, 68, 216, 36, maxl=70),
        text("tstat", 28, 104, 216, 36, maxl=70, pco=GREY565),
        button("bc", 18, 164, 236, 40, "", 1, "net_bg_detail", "net_bg_detail_p", maxl=40),
        button("bp", 18, 214, 236, 40, "", 2, "net_bg_detail", "net_bg_detail_p"),
        button("ba", 18, 264, 236, 40, "", 3, "net_bg_detail", "net_bg_detail_p"),
        button("bf", 18, 314, 236, 40, "", 4, "net_bg_detail", "net_bg_detail_p"),
    ]
    pages["net_detail"] = page("net_detail", "net_bg_detail", objs, i18n({
        "t6.txt": ("Network", "Сеть"),
        "bp.txt": ("Change password", "Изменить пароль"),
        "bf.txt": ("Forget network", "Забыть сеть"),
    }))

    # net_confirm
    objs = common("Forget network") + [
        text("tmsg", 28, 80, 216, 160, maxl=120, xcen=1, ycen=1),
        button("byes", 18, 280, 112, 48, "", 1, "net_bg_confirm", "net_bg_confirm_p"),
        button("bno", 142, 280, 112, 48, "", 0, "net_bg_confirm", "net_bg_confirm_p"),
    ]
    pages["net_confirm"] = page("net_confirm", "net_bg_confirm", objs, i18n({
        "t6.txt": ("Forget network", "Забыть сеть"),
        "byes.txt": ("Forget", "Забыть"),
        "bno.txt": ("Cancel", "Отмена"),
    }))

    # net_info
    objs = common("Network info") + [
        text("twifi", 28, 70, 216, 130, maxl=200, ycen=0),
        text("teth", 28, 220, 216, 130, maxl=200, ycen=0),
        button("bwifi", 18, 364, 236, 40, "", 1, "net_bg_info", "net_bg_info_p", maxl=30),
    ]
    pages["net_info"] = page("net_info", "net_bg_info", objs, i18n({"t6.txt": ("Network info", "Сведения о сети")}))
    return pages


# ---------------------------------------------------------------------------------------------- edits of old pages
def edit_wifi_list():
    p = load("pages/wifi_list.json")
    p["root"]["attributes"]["pic"] = ref("picture", "net_bg_list")
    p["objects"] = [o for o in p["objects"] if o["key"] != "t0"]       # the address moved to the info page
    p["objects"] += [button("bsaved", 18, 64, 90, 40, "", 8, "net_bg_list", "net_bg_list_p", maxl=20),
                     button("bhidden", 114, 64, 90, 40, "", 9, "net_bg_list", "net_bg_list_p", maxl=20)]
    p["root"]["events"]["codesload"] = i18n({"bsaved.txt": ("Saved", "Сохр."), "bhidden.txt": ("Hidden", "Скрытая")})
    save("pages/wifi_list.json", p)


def edit_wifi_kb():
    p = load("pages/wifi_kb.json")
    for o in p["objects"]:
        if o["key"] == "b31":
            o["events"]["codesup"] = ["if(temp.val>=kbmin)", "{", "  prints 112,1", "  prints kbmode,1", "  prints sys2,1",
                                      "  prints show.txt,0", "}"]
        elif o["key"] == "tm0":
            o["events"]["codestimer"] = ["btlen input.txt,temp.val", "if(temp.val<kbmin)", "{",
                                         "  b31.picc=${picture:pic_103}", "}else", "{", "  b31.picc=${picture:pic_102}", "}"]
    save("pages/wifi_kb.json", p)


def edit_internet_page():
    p = load("pages/internet_page.json")
    p["root"]["attributes"]["pic"] = ref("picture", "net_bg_internet")
    p["objects"] = [o for o in p["objects"] if o["key"] not in ("b4", "t4", "b8", "t8")]
    for o in p["objects"]:
        if o["key"] in ("b5", "b6", "b7"):
            o["attributes"]["picc"] = ref("picture", "net_bg_internet")
    p["root"]["events"]["codesload"] = i18n({
        "t1.txt": ("Network", "Сеть"),
        "t5.txt": ("Network info", "Сведения о сети"),
        "t6.txt": ("Saved networks", "Сохранённые сети"),
        "t7.txt": ("Hidden network", "Скрытая сеть"),
    })
    for o in p["objects"]:
        if o["key"] == "t5":
            o["attributes"]["txt"] = "Network info"
        elif o["key"] == "t6":
            o["attributes"]["txt"] = "Saved networks"
        elif o["key"] == "t7":
            o["attributes"]["txt"] = "Hidden network"
    save("pages/internet_page.json", p)


def edit_program():
    s = open("Program.s", encoding="utf-8").read()
    marker = "int sleep_counts=0\n"
    assert marker in s
    s = s.replace(marker, marker + "int kbmode=1,kbmin=8\n", 1)
    open("Program.s", "w", encoding="utf-8").write(s)


def main():
    pj = load("project.json")
    if any(p["key"] == "net_saved" for p in pj["pages"]):
        sys.exit("already applied")
    for key, im in make_pictures().items():
        im.save("pictures/%s.png" % key)
        pj["pictures"].append({"key": key, "source": {"png": "pictures/%s.png" % key}})
    for key, data in build_pages().items():
        save("pages/%s.json" % key, data)
        pj["pages"].append({"key": key, "content": {"mode": "json", "path": "pages/%s.json" % key}})
    edit_wifi_list()
    edit_wifi_kb()
    edit_internet_page()
    edit_program()
    save("project.json", pj)


if __name__ == "__main__":
    main()
