#!/usr/bin/env python3
"""(One-off migration, written for the former librescreen/event.py; its function names are gone.)
Rewrites the component names that the Python librescreen writes in instructions for the screen, following tools/names.json.

    python3 display_firmware/tools/rename_host.py [--apply]       (run from src_py/)

The host addresses components by name ("t0", "n3", "preview.cp0", ...), always for one page of the screen; the page
is known from the function (FUNC_PAGES) and from the code around: ``page_to(ui.TJC_PAGE_X)`` makes the following
statements of the same block address page X, ``if g.current_page_id == ui.TJC_PAGE_X`` addresses X inside. Every
string literal equal to an old component name of the page in effect is replaced; the plan is printed, string literals
that look like component names but are not on the page in effect are listed as warnings (stale names of the
original, nothing to rename).
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(ROOT, "..", ".."))            # src_py/
FW = os.path.join(SRC, "display_firmware")
NAMES = json.load(open(os.path.join(ROOT, "names.json"), encoding="utf-8"))["pages"]
PROJECT = json.load(open(os.path.join(FW, "project.json"), encoding="utf-8"))
PAGES = [p["key"] for p in PROJECT["pages"]]

# pages addressed by the code of a function (nothing: the code switches the page itself first)
FUNC_PAGES = {
    "refresh_page_show": [],
    "refresh_page_open_filament_video_2": ["filamentVideo2"],
    "refresh_page_wifi_keyboard": ["wifi_kb"],
    "refresh_page_print_filament": ["print_filament"],
    "refresh_page_auto_moving": ["auto_moving"],
    "refresh_page_move": ["move"],
    "refresh_page_printing_zoffset": ["print_zoffset"],
    "refresh_page_printing": ["printing", "keybdB", "printing_2"],
    "_send_chunks_txt": ["preview"],
    "refresh_page_preview": ["preview"],
    "refresh_page_main": ["main"],
    "refresh_page_files_list": ["filelist"],
    "go_to_reset": [],
    "refresh_page_wifi_list": ["wifi_list"],
    "filament_load": ["filament_pop_2", "filament_pop_3"],
    "refresh_page_auto_heaterbed": ["auto_heaterbed"],
    "refresh_page_open_heaterbed": ["open_heaterbed"],
    "refresh_page_filament_pop": ["filament_pop_2", "filament_pop_3"],
    "refresh_page_preview_pop": ["preview_pop_1", "preview_pop_2"],
    "go_to_update": [],
    "refresh_page_filament_set_fan": ["fila_set_fan"],
    "refresh_page_common_setting": ["common_set"],
    "refresh_page_filament": ["filament"],
    "refresh_ip_address": [],
    "refresh_page_show_ip": ["internet_page"],
    "refresh_page_server_set": ["server_set"],
    "check_online_version": [],
    "online_update": [],
    "recevice_progress_handle": ["updating"],
    "refresh_page_auto_unload": ["auto_unload"],
    "tjc_event_setted_handler": [],
    "clear_cp0_image": [],
    "refresh_page_zoffset": ["zoffset"],
    "_zoffset_buttons": ["print_zoffset"],
    "refresh_page_auto_level": ["pre_bed_cal"],
}
# a condition that mentions one of these constants addresses that page in its body
CONDITION_PAGES = {
    "TJC_PAGE_PRINTING_2_SPEED": ["printing_2"],        # the keyboard reports page 20 for the values of page 24
    "TJC_PAGE_PRINTING_2_FLOW": ["printing_2"],
    "printing_keyboard_enabled": ["keybdB"],
}
# dynamic names: (file, function, old source, new source)
DYNAMIC = [
    ("event.py", "refresh_page_files_list", '"b" + to_string(i + 1)', '"file" + to_string(i + 1)'),
    ("event.py", "refresh_page_files_list", '"t" + to_string(i + 1)', '"file" + to_string(i + 1) + "_name"'),
    ("event.py", "refresh_page_wifi_list", '"wifi" + to_string(i + 1)', '"row" + to_string(i + 1)'),
    ("event.py", "refresh_page_wifi_list", '"t" + to_string(i + 1)', '"row" + to_string(i + 1) + "_txt"'),
    ("event.py", "refresh_page_zoffset", '"t" + to_string(5 * i + j)', '"cell_" + to_string(5 * i + j)'),
    ("event.py", "_zoffset_buttons", '"b" + to_string(b)', '("step_001", "step_005", "step_01", "step_05")[b - 1]'),
    ("event.py", "refresh_page_server_set", '"b" + to_string(i + 5)', '"srv" + to_string(i + 1)'),
    ("event.py", "refresh_page_server_set", '"t" + to_string(i + 5)', '"srv" + to_string(i + 1) + "_txt"'),
    ("event.py", "check_online_version", '"t_" + lang', '"notes_" + lang'),
]


def page_constants():
    """ui.TJC_PAGE_X names that are page ids (used with page_to / comparisons) -> page key."""
    ui = open(os.path.join(SRC, "librescreen", "ui.py"), encoding="utf-8").read()
    values = {m.group(1): int(m.group(2), 0) for m in re.finditer(r"^(TJC_PAGE_\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)", ui, re.M)}
    out = {}
    for name in set(re.findall(r"page_to\((?:ui\.)?(TJC_PAGE_\w+)\)", ui + open(os.path.join(SRC, "librescreen", "event.py")).read())):
        if name in values and values[name] < len(PAGES):
            out[name] = PAGES[values[name]]
    for name in set(re.findall(r"(?:page_id|current_page_id|page) == (?:ui\.)?(TJC_PAGE_\w+)", ui + open(os.path.join(SRC, "librescreen", "event.py")).read())):
        if name in values and values[name] < len(PAGES):
            out.setdefault(name, PAGES[values[name]])
    return out


PAGE_CONST = page_constants()
OLD = {p: set(m) for p, m in NAMES.items()}


def const_name(node):
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def test_pages(test):
    """Pages addressed inside the body of an ``if`` with this condition (None: no change)."""
    pages = []
    for n in ast.walk(test):
        name = const_name(n)
        if name in CONDITION_PAGES:
            pages += CONDITION_PAGES[name]
    for n in ast.walk(test):
        if isinstance(n, ast.Compare) and any(isinstance(op, (ast.Eq, ast.In)) for op in n.ops):
            for m in ast.walk(n):
                name = const_name(m)
                if name in PAGE_CONST:
                    pages.append(PAGE_CONST[name])
    return pages or None


def page_to_target(stmt):
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        f = stmt.value.func
        if getattr(f, "id", getattr(f, "attr", "")) == "page_to" and stmt.value.args:
            name = const_name(stmt.value.args[0])
            if name in PAGE_CONST:
                return [PAGE_CONST[name]]
    return None


class Plan:
    def __init__(self, path):
        self.path = path
        self.edits = []       # (lineno, col, end_col, old_text, new_text, function, pages)
        self.warnings = []

    def literal(self, node, func, pages):
        value = node.value
        m = re.match(r"^(\w+)\.(\w+)$", value)
        if m and m.group(1) in NAMES and m.group(2) in NAMES[m.group(1)]:        # "preview.cp0"
            new = "%s.%s" % (m.group(1), NAMES[m.group(1)][m.group(2)])
            self.edits.append((node, new, func, [m.group(1)]))
            return
        if not pages:
            return
        hits = [p for p in pages if value in OLD.get(p, ())]
        if hits:
            news = {NAMES[p][value] for p in hits}
            if len(news) != 1:
                self.warnings.append("%s:%d %s: %r renamed differently on %s" % (self.path, node.lineno, func, value, hits))
                return
            missing = [p for p in pages if value not in OLD.get(p, ())]
            if missing:
                self.warnings.append("%s:%d %s: %r is a component of %s but not of %s" % (self.path, node.lineno, func, value, hits, missing))
            self.edits.append((node, news.pop(), func, hits))
        elif re.match(r"^(b|t|n|q|h|j|gm|cp|tm|va|exp)\d+$|^v999$", value):
            self.warnings.append("%s:%d %s: %r does not exist on %s" % (self.path, node.lineno, func, value, pages))

    def block(self, stmts, func, pages):
        for stmt in stmts:
            self.statement(stmt, func, pages)
            target = page_to_target(stmt)
            if target:
                pages = target

    def statement(self, stmt, func, pages):
        if isinstance(stmt, ast.If):
            self.expr(stmt.test, func, pages)
            inner = test_pages(stmt.test) or pages
            self.block(stmt.body, func, inner)
            self.block(stmt.orelse, func, pages)
        elif isinstance(stmt, (ast.For, ast.While, ast.With, ast.Try)):
            for field in ("iter", "test"):
                if hasattr(stmt, field):
                    self.expr(getattr(stmt, field), func, pages)
            for field in ("body", "orelse", "finalbody"):
                self.block(getattr(stmt, field, []), func, pages)
            for h in getattr(stmt, "handlers", []):
                self.block(h.body, func, pages)
        elif isinstance(stmt, ast.FunctionDef):
            pass        # nested functions are handled as their own entries
        else:
            self.expr(stmt, func, pages)

    def expr(self, node, func, pages):
        for n in ast.walk(node):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                self.literal(n, func, pages)


def plan_file(name):
    path = os.path.join(SRC, "librescreen", name)
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    plan = Plan(name)
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        if fn.name in FUNC_PAGES:
            plan.block(fn.body, fn.name, FUNC_PAGES[fn.name])
    return path, src, plan


def apply_edits(src, plan, name):
    lines = src.split("\n")
    # byte offsets of the line starts
    starts = [0]
    for l in lines:
        starts.append(starts[-1] + len(l.encode("utf-8")) + 1)
    data = src.encode("utf-8")
    repl = []
    for node, new, func, pages in plan.edits:
        a = starts[node.lineno - 1] + node.col_offset
        b = starts[node.end_lineno - 1] + node.end_col_offset
        old_text = data[a:b].decode("utf-8")
        quote = old_text[0]
        repl.append((a, b, quote + new + quote))
    for f, fn, old, new in DYNAMIC:
        if f != name:
            continue
        tree = ast.parse(src)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn)
        a0 = starts[func.lineno - 1]
        b0 = starts[func.end_lineno]
        seg = data[a0:b0].decode("utf-8")
        count = seg.count(old)
        if count == 0:
            raise SystemExit("%s: %s: %r not found" % (name, fn, old))
        pos = 0
        for _ in range(count):
            i = seg.index(old, pos)
            pos = i + len(old)
            repl.append((a0 + len(seg[:i].encode("utf-8")), a0 + len(seg[:i + len(old)].encode("utf-8")), new))
    repl.sort(reverse=True)
    for a, b, text in repl:
        data = data[:a] + text.encode("utf-8") + data[b:]
    return data.decode("utf-8"), len(repl)


def verify():
    """After the renaming: every string that is a component name of some page has to exist on the pages in effect."""
    objects = {}
    for p in PROJECT["pages"]:
        d = json.load(open(os.path.join(FW, p["content"]["path"]), encoding="utf-8"))
        objects[p["key"]] = {o["attributes"]["objname"] for o in d["objects"]}
    everywhere = set().union(*objects.values()) - {"touch", "sleep_counter", "input", "temp", "show", "refresh", "output"}

    class Check(Plan):
        def literal(self, node, func, pages):
            value = node.value
            m = re.match(r"^(\w+)\.(\w+)$", value)
            if m and m.group(1) in objects:
                if m.group(2) not in objects[m.group(1)]:
                    self.warnings.append("%s:%d %s: %r does not exist" % (self.path, node.lineno, func, value))
                return
            if value in everywhere and pages:
                missing = [p for p in pages if value not in objects[p]]
                if missing:
                    self.warnings.append("%s:%d %s: %r is not a component of %s" % (self.path, node.lineno, func, value, missing))
            elif value in everywhere and not pages:
                self.warnings.append("%s:%d %s: %r used without a known page" % (self.path, node.lineno, func, value))

    bad = 0
    for name in sorted(f for f in os.listdir(os.path.join(SRC, "librescreen")) if f.endswith(".py")):
        tree = ast.parse(open(os.path.join(SRC, "librescreen", name), encoding="utf-8").read())
        plan = Check(name)
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            if fn.name in FUNC_PAGES:
                plan.block(fn.body, fn.name, FUNC_PAGES[fn.name])
        for w in plan.warnings:
            print("warning:", w)
            bad += 1
    print("verify: %d warnings" % bad)


def main():
    if "--verify" in sys.argv:
        return verify()
    apply = "--apply" in sys.argv
    total = 0
    for name in sorted(f for f in os.listdir(os.path.join(SRC, "librescreen")) if f.endswith(".py")):
        path, src, plan = plan_file(name)
        if not plan.edits and not any(d[0] == name for d in DYNAMIC):
            continue
        new, count = apply_edits(src, plan, name)
        total += count
        for w in plan.warnings:
            print("warning:", w)
        if "--verbose" in sys.argv:
            seen = {}
            for node, new, func, pages in plan.edits:
                seen.setdefault((func, ",".join(pages)), set()).add("%s>%s" % (node.value, new))
            for (func, pages), v in seen.items():
                print("  %s [%s]: %s" % (func, pages, " ".join(sorted(v))))
        if apply:
            open(path, "w", encoding="utf-8").write(new)
        print("%s: %d replacements" % (name, count))
    print("total", total)


if __name__ == "__main__":
    main()
