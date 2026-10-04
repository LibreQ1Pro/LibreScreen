"""Names for the tiles of a Plan.

A button and its pressed look are named together (``name`` and ``name_press``). A look the host switches is named
after its page, widget group and state (``filament_toggle_on``); a widget of the group whose tile differs from the
others gets its own name (``filament_nozzle_toggle_on``). The tile of a button that shows one picture is named after
the widget (``internet_page_saved_btn``, or just ``nav_files`` when several pages use the same one). When two
different tiles want one name, the page, then the size, then a number tell them apart.
"""
SIZE = "%dx%d"


class Namer(object):
    def __init__(self, plan, taken):
        self.plan = plan
        self.used = set(taken)
        self.names = {}

    def size(self, digest):
        return SIZE % self.plan.tiles[digest]["image"].size

    def free(self, name, pressed):
        return name not in self.used and (not pressed or name + "_press" not in self.used)

    def claim(self, candidates, normal, pressed):
        """Gives the first free candidate to the tile ``normal`` and candidate + _press to ``pressed``."""
        for name in candidates + ["%s_%d" % (candidates[-1], n) for n in range(2, 99)]:
            if self.free(name, pressed and pressed not in self.names):
                break
        if normal not in self.names:
            self.names[normal] = name
            self.used.add(name)
        if pressed and pressed not in self.names:
            self.names[pressed] = name + "_press"
            self.used.add(name + "_press")

    def variants(self, base, page, digest):
        """base, then with the page, then with the size."""
        out = [base]
        if not base.startswith(page):
            out.append("%s_%s" % (page, base))
        out.append("%s_%s" % (out[-1], self.size(digest)))
        return out

    def run(self):
        plan = self.plan
        blank = [d for d in plan.tiles if d.startswith("blank_")]
        for d in blank:
            self.names[d] = d
            self.used.add(d)
        # the looks the host switches
        from tile_spec import SPEC
        for page, group, widgets, states in SPEC:
            for state in states:
                for widget in widgets:
                    one, two = plan.states[(widget, state)][page]
                    same = all(plan.states[(w, state)][page] == (one, two) for w in widgets)
                    base = "%s_%s_%s" % (page, group, state) if same else "%s_%s_%s" % (page, widget, state)
                    self.claim(self.variants(base, page, one), one, two)
        # the buttons that show one picture, named after the widget; the tiles of a widget that more than one page has
        # identically are named without the page
        users = {}
        for (page, widget), entry in plan.static.items():
            if entry:
                users.setdefault((widget, entry.get("picc"), entry.get("picc2")), []).append(page)
        for (page, widget), entry in sorted(plan.static.items()):
            if not entry or entry["picc"] in self.names and entry.get("picc2", entry["picc"]) in self.names:
                continue
            pages = users[(widget, entry.get("picc"), entry.get("picc2"))]
            base = widget if len(pages) > 1 else "%s_%s" % (page, widget)
            self.claim(self.variants(base, page, entry["picc"]), entry["picc"], entry.get("picc2"))
        # what the screen's own code switches to: named after the widget and the old sheet
        for digest, tile in plan.tiles.items():
            if digest not in self.names:
                page, widget, sheet, _ = tile["uses"][0]
                words = []
                for word in ("%s_%s_%s" % (page, widget, sheet)).split("_"):
                    if word not in words:
                        words.append(word)
                self.claim(self.variants("_".join(words), page, digest), digest, None)
        return self.names


def assign(plan, taken):
    """digest -> unique readable name (``taken``: the names that exist already)."""
    return Namer(plan, taken).run()
