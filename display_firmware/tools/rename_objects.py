#!/usr/bin/env python3
"""Renames components, pictures, fonts and animations of the portable project.

    python3 tools/rename_objects.py names.json            apply (in place; run from display_firmware/)
    python3 tools/rename_objects.py names.json --check    only validate and verify, change nothing

names.json: {"pages": {PAGE_KEY: {old_objname: new_objname}},
             "pictures": {old_key: new_key}, "fonts": {...}, "animations": {...}}

Components: the ``key`` and ``objname`` of the object and every reference in event code are rewritten (``x.txt``,
``click x,1``, ``vis x,0``, ``page.x.val`` of other pages, ``${obj:PAGE/x}`` placeholders). Positions in the lists do not
change, so the runtime ids of pages, components and pictures stay the same: the host (which sends picture ids and
reads ``0x65 <page> <action>`` frames) is not affected, only the names it writes in instructions are.

Every run verifies itself: the names are valid for the editor (letters, digits, ``_``; at most 14 bytes; unique per
page; no clash with a page name or a global variable), and applying the inverse renaming to the result gives back the
original project byte for byte.
"""
import copy
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = re.compile(r"(?<![\w.])([A-Za-z_]\w*)(?:\.([A-Za-z_]\w*))?")
PLACEHOLDER = re.compile(r"\$\{(\w+):([^}]*)\}")
NAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,13}$")


def split_code(line):
    """Pieces of an instruction line: (True, code) outside string literals / comments, (False, text) inside."""
    out, i, n = [], 0, len(line)
    while i < n:
        if line[i] == '"':
            j = i + 1
            while j < n and line[j] != '"':
                j += 2 if line[j] == "\\" else 1
            out.append((False, line[i:j + 1]))
            i = j + 1
        elif line.startswith("//", i):
            out.append((False, line[i:]))
            i = n
        else:
            j = i
            while j < n and line[j] != '"' and not line.startswith("//", j):
                j += 1
            out.append((True, line[i:j]))
            i = j
    return out


class Renamer:
    def __init__(self, names):
        self.obj = names.get("pages", {})          # page -> {old: new}
        self.res = {"picture": names.get("pictures", {}), "font": names.get("fonts", {}),
                    "animation": names.get("animations", {})}

    def inverse(self):
        inv = {"pages": {p: {v: k for k, v in m.items()} for p, m in self.obj.items()}}
        for kind, key in (("picture", "pictures"), ("font", "fonts"), ("animation", "animations")):
            inv[key] = {v: k for k, v in self.res[kind].items()}
        return Renamer(inv)

    # ------------------------------------------------------------------------------ code
    def code(self, line, page):
        local = self.obj.get(page, {})

        def placeholder(m):
            kind, arg = m.group(1), m.group(2)
            if kind in ("obj", "objname"):
                p, _, o = arg.partition("/")
                return "${%s:%s/%s}" % (kind, p, self.obj.get(p, {}).get(o, o))
            if kind in self.res:
                return "${%s:%s}" % (kind, self.res[kind].get(arg, arg))
            return m.group(0)

        def ident(m):
            first, second = m.group(1), m.group(2)
            if second is not None and first in self.obj and second in self.obj[first]:
                return "%s.%s" % (first, self.obj[first][second])
            if first in local:
                return m.group(0).replace(first, local[first], 1)
            return m.group(0)

        out = []
        for is_code, text in split_code(line):
            if not is_code:
                out.append(text)
                continue
            parts, pos = [], 0
            for m in PLACEHOLDER.finditer(text):
                parts.append(CODE.sub(ident, text[pos:m.start()]))
                parts.append(placeholder(m))
                pos = m.end()
            parts.append(CODE.sub(ident, text[pos:]))
            out.append("".join(parts))
        return "".join(out)

    def program(self, text):
        def placeholder(m):
            kind, arg = m.group(1), m.group(2)
            if kind in self.res:
                return "${%s:%s}" % (kind, self.res[kind].get(arg, arg))
            return m.group(0)
        return PLACEHOLDER.sub(placeholder, text)

    # ------------------------------------------------------------------------------ json
    def refs(self, node):
        if isinstance(node, dict):
            if set(node) == {"$ref"}:
                kind, _, key = node["$ref"].partition(":")
                if kind in self.res:
                    return {"$ref": "%s:%s" % (kind, self.res[kind].get(key, key))}
                return node
            return {k: self.refs(v) for k, v in node.items()}
        if isinstance(node, list):
            return [self.refs(v) for v in node]
        return node

    def page(self, key, data):
        data = copy.deepcopy(data)
        local = self.obj.get(key, {})
        data["root"]["attributes"] = self.refs(data["root"]["attributes"])
        data["root"]["events"] = {k: [self.code(l, data["name"]) for l in v] for k, v in data["root"]["events"].items()}
        for o in data["objects"]:
            old = o["key"]
            o["key"] = local.get(old, old)
            o["attributes"] = self.refs(o["attributes"])
            if o["attributes"].get("objname") == old:
                o["attributes"]["objname"] = o["key"]
            o["events"] = {k: [self.code(l, data["name"]) for l in v] for k, v in o["events"].items()}
        return data


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def dump(path, data):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_project():
    project = load("project.json")
    pages = {p["key"]: load(p["content"]["path"]) for p in project["pages"]}
    program = open(os.path.join(ROOT, "Program.s"), encoding="utf-8").read()
    return project, pages, program


def transform(project, pages, program, r):
    """The renamed (project, pages, program); file names are not touched here."""
    project = copy.deepcopy(project)
    for kind, lst in (("picture", "pictures"), ("font", "fonts"), ("animation", "animations")):
        for item in project[lst]:
            item["key"] = r.res[kind].get(item["key"], item["key"])
    project = r.refs(project)
    return project, {k: r.page(k, d) for k, d in pages.items()}, r.program(program)


def validate(project, pages, names):
    problems = []
    page_names = set(pages)
    reserved = {"dp", "dim", "dims", "sleep", "bauds", "thsp", "thup", "sys0", "sys1", "sys2", "lang", "page", "if", "else",
                "for", "while", "click", "vis", "tsw", "ref", "prints", "printh", "covx", "cov", "get", "val", "txt", "pic",
                "picc", "pco", "bco", "font", "en", "id", "x", "y", "w", "h"}
    for key, data in pages.items():
        seen = set()
        for o in data["objects"]:
            n = o["attributes"]["objname"]
            if not NAME_OK.match(n):
                problems.append("%s: bad name %r" % (key, n))
            if n in seen:
                problems.append("%s: duplicate name %r" % (key, n))
            seen.add(n)
            if n in page_names or n in reserved:
                problems.append("%s: %r clashes with a page name / reserved word" % (key, n))
            if o["key"] != n:
                problems.append("%s: key %r differs from objname %r" % (key, o["key"], n))
    for kind, lst in (("pictures", "pictures"), ("fonts", "fonts"), ("animations", "animations")):
        keys = [i["key"] for i in project[lst]]
        if len(keys) != len(set(keys)):
            problems.append("duplicate %s keys" % kind)
    return problems


def stale_references(new_pages, names):
    """Event code that still mentions an old component name which was renamed (a reference the rewrite missed)."""
    stale = []
    for key, data in new_pages.items():
        local_old = {o for o, n in names.get("pages", {}).get(key, {}).items() if o != n}
        new_names = {o["attributes"]["objname"] for o in data["objects"]}
        lines = [("root", l) for v in data["root"]["events"].values() for l in v]
        lines += [(o["key"], l) for o in data["objects"] for v in o["events"].values() for l in v]
        for where, line in lines:
            for is_code, text in split_code(line):
                if not is_code:
                    continue
                text = PLACEHOLDER.sub(" ", text)
                for m in CODE.finditer(text):
                    first, second = m.group(1), m.group(2)
                    if second is not None and first in names.get("pages", {}):
                        if second in names["pages"][first] and names["pages"][first][second] != second \
                                and second not in {o["attributes"]["objname"] for o in new_pages[first]["objects"]}:
                            stale.append("%s/%s: %s" % (key, where, line.strip()))
                    elif first in local_old and first not in new_names:
                        stale.append("%s/%s: %s" % (key, where, line.strip()))
    return stale


def apply_files(project, old_project):
    """Moves the picture / font / animation files to the new key names; returns the moves."""
    moves = []
    for lst, folder, ext in (("pictures", "pictures", ".png"), ("fonts", "fonts", ".zi")):
        for old, new in zip(old_project[lst], project[lst]):
            if old["key"] != new["key"]:
                moves.append((os.path.join(folder, old["key"] + ext), os.path.join(folder, new["key"] + ext)))
    for old, new in zip(old_project["animations"], project["animations"]):
        if old["key"] != new["key"]:
            moves.append((os.path.join("animations", old["key"]), os.path.join("animations", new["key"])))
    return moves


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_only = "--check" in sys.argv
    names = json.load(open(args[0], encoding="utf-8"))
    r = Renamer(names)
    project, pages, program = read_project()
    new_project, new_pages, new_program = transform(project, pages, program, r)

    problems = validate(new_project, new_pages, names)
    # old names that are still addressed in code must exist (a typo in names.json would rename a name that is not there)
    for key, m in names.get("pages", {}).items():
        existing = {o["attributes"]["objname"] for o in pages[key]["objects"]}
        for old in m:
            if old not in existing:
                problems.append("%s: no component %r" % (key, old))
    problems += ["stale reference: " + x for x in stale_references(new_pages, names)]
    # the inverse renaming has to give the original project back
    back_project, back_pages, back_program = transform(new_project, new_pages, new_program, r.inverse())
    if back_project != project or back_pages != pages or back_program != program:
        problems.append("the inverse renaming does not reproduce the original project")
    if problems:
        sys.exit("\n".join(problems))
    changed = sum(1 for k in pages if pages[k] != new_pages[k])
    print("ok: %d pages changed, %d components renamed, %d pictures, %d fonts, %d animations"
          % (changed, sum(len(m) for m in names.get("pages", {}).values()), len(names.get("pictures", {})),
             len(names.get("fonts", {})), len(names.get("animations", {}))))
    if check_only:
        return
    for src, dst in apply_files(new_project, project):
        os.rename(os.path.join(ROOT, src), os.path.join(ROOT, dst))
    for lst, folder, ext in (("pictures", "pictures", ".png"), ("fonts", "fonts", ".zi")):
        for item in new_project[lst]:
            for k, v in list(item.get("source", {}).items()):
                if isinstance(v, str) and v.startswith(folder + "/"):
                    item["source"][k] = "%s/%s%s" % (folder, item["key"], ext)
    for item in new_project["animations"]:
        for frame in item.get("frames", []):
            frame["png"] = re.sub(r"^animations/[^/]+/", "animations/%s/" % item["key"], frame["png"])
        for k in ("gmov", "gmovs"):
            if isinstance(item.get(k), str):
                item[k] = re.sub(r"^animations/[^/]+/", "animations/%s/" % item["key"], item[k])
    dump("project.json", new_project)
    for key, data in new_pages.items():
        dump(next(p["content"]["path"] for p in new_project["pages"] if p["key"] == key), data)
    open(os.path.join(ROOT, "Program.s"), "w", encoding="utf-8").write(new_program)


if __name__ == "__main__":
    main()
