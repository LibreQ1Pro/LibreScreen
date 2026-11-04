#!/usr/bin/env python3
"""Writes the fixed texts of the network pages in all 13 screen languages.

    python3 tools/net_i18n.py            apply (run from display_firmware/)
    python3 tools/net_i18n.py --check    only report what would change

The texts come from librescreen/util/netstrings.py (the host uses the same table for the texts that depend on the state). For every
page the ``codesload`` event becomes the usual ``if(lang==0){...}else if(lang==1){...}`` chain of the stock pages, and the
text of the component in the editor is the English one. The pages listed here have no other code in ``codesload``.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
from librescreen.util.netstrings import TEXT, LANGUAGES    # noqa: E402

ENGLISH = LANGUAGES.index("en")
PAGES = {
    "net_saved": {"title": "saved_networks"},
    "net_detail": {"title": "network", "passwd_btn": "change_password", "forget_btn": "forget_network"},
    "net_confirm": {"title": "forget_network", "forget_btn": "forget", "cancel": "cancel"},
    "net_info": {"title": "network"},
    "wifi_list": {"saved_btn": "saved_short", "hidden_btn": "hidden_short"},
    "internet_page": {"title": "network", "info_lbl": "network_info", "saved_lbl": "saved_networks",
                      "hidden_lbl": "hidden_network"},
}


def chain(texts):
    """The codesload lines for {object: [text per language]}."""
    lines = []
    for lang in range(len(LANGUAGES)):
        lines += ["%sif(lang==%d)" % ("}else " if lang else "", lang), "{"]
        lines += ['  %s.txt="%s"' % (obj, row[lang]) for obj, row in texts.items()]
    return lines + ["}"]


def main():
    check = "--check" in sys.argv
    changed = 0
    for page, objects in PAGES.items():
        path = os.path.join(ROOT, "pages", page + ".json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        before = json.dumps(data, sort_keys=True)
        data["root"]["events"]["codesload"] = chain({o: TEXT[k] for o, k in objects.items()})
        for o in data["objects"]:
            if o["key"] in objects:
                o["attributes"]["txt"] = TEXT[objects[o["key"]]][ENGLISH]
        if json.dumps(data, sort_keys=True) != before:
            changed += 1
            if not check:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write("\n")
    print("%d pages %s" % (changed, "would change" if check else "written"))


if __name__ == "__main__":
    main()
