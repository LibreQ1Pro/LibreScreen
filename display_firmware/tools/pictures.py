#!/usr/bin/env python3
"""Helpers to add, rename and remove pictures of the screen project (a library for the scripts of this directory).

    from pictures import Pictures
    p = Pictures()
    p.add("fan_slider_track", "/path/track.png")      # copies the file to pictures/<key>.png, appends the key
    p.rename("hdr_back_press", "header_back_press")  # file, project.json, every reference, names.json
    p.remove(["unused_one"])                          # refuses while the picture is still referenced
    p.save()                                          # writes project.json and librescreen/screen/faces.py

The id of a picture is its position in ``project.json``. The host sends the ids of the looks of its widgets from
librescreen/screen/faces.py, which gen_faces.py writes from tools/faces.json (save() runs it). A reference is
``"$ref": "picture:KEY"`` in the pages and ``${picture:KEY}`` in their code.
"""
import glob
import json
import os
import re
import shutil

import gen_faces

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # display_firmware/


def reference(key):
    """Regex of the references to the picture ``key`` (the key may be a prefix of another one)."""
    return re.compile(r"picture:%s(?![A-Za-z0-9_])" % re.escape(key))


class Pictures(object):
    def __init__(self):
        with open(os.path.join(ROOT, "project.json"), encoding="utf-8") as f:
            self.project = json.load(f)
        self.raw = open(os.path.join(ROOT, "project.json"), encoding="utf-8").read()

    def keys(self):
        return [p["key"] for p in self.project["pictures"]]

    def pages(self):
        return sorted(glob.glob(os.path.join(ROOT, "pages", "*.json")))

    def users(self, key):
        """The page files that refer to the picture."""
        rx = reference(key)
        found = []
        for path in self.pages():
            with open(path, encoding="utf-8") as f:
                if rx.search(f.read()):
                    found.append(os.path.basename(path))
        return found

    def add(self, key, png, index=None):
        if key in self.keys():
            raise ValueError("picture %s exists" % key)
        dest = os.path.join(ROOT, "pictures", key + ".png")
        if os.path.abspath(png) != os.path.abspath(dest):
            shutil.copy(png, dest)
        entry = {"key": key, "source": {"png": "pictures/%s.png" % key}}
        if index is None:
            self.project["pictures"].append(entry)
        else:
            self.project["pictures"].insert(index, entry)

    def remove(self, keys):
        for key in keys:
            used = self.users(key)
            if used:
                raise ValueError("picture %s is still used by %s" % (key, ", ".join(used)))
        gone = set(keys)
        self.project["pictures"] = [p for p in self.project["pictures"] if p["key"] not in gone]
        for key in keys:
            path = os.path.join(ROOT, "pictures", key + ".png")
            if os.path.exists(path):
                os.remove(path)

    def rename(self, old, new):
        if new in self.keys():
            raise ValueError("picture %s exists" % new)
        for entry in self.project["pictures"]:
            if entry["key"] == old:
                entry["key"] = new
                entry["source"]["png"] = "pictures/%s.png" % new
        src, dest = (os.path.join(ROOT, "pictures", k + ".png") for k in (old, new))
        if os.path.exists(src):
            os.rename(src, dest)
        rx = reference(old)
        for path in self.pages():
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if rx.search(text):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(rx.sub("picture:" + new, text))
        faces = os.path.join(ROOT, "tools", "faces.json")
        with open(faces, encoding="utf-8") as f:
            looks = json.load(f)
        for states in looks.values():
            for state, tiles in states.items():
                states[state] = [new if t == old else t for t in tiles]
        with open(faces, "w", encoding="utf-8") as f:
            json.dump(looks, f, indent=1, ensure_ascii=False)
            f.write("\n")
        names = os.path.join(ROOT, "tools", "names.json")
        with open(names, encoding="utf-8") as f:
            data = json.load(f)
        for stock, readable in data["pictures"].items():
            if readable == old:
                data["pictures"][stock] = new
        with open(names, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")

    def save(self):
        with open(os.path.join(ROOT, "project.json"), "w", encoding="utf-8") as f:
            json.dump(self.project, f, ensure_ascii=False, indent=2)
            f.write("\n")
        gen_faces.main()                         # the ids of the looks of the host moved with the pictures
