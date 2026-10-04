#!/usr/bin/env python3
"""Snaps every #rrggbb colour of the mockup (mockup/src/*.css, *.js) to a colour the screen can show exactly (RGB565).

    python3 tools/snap_palette.py [--dry-run]            (run from display_firmware/)

The screen keeps 5 bits of red and blue and 6 of green, so most colours of a design drawn in 8 bits move a little, and the three channels move by different
amounts (a dark grey turns blue or green). Here the nearest colour that is exact is chosen so that the grey stays a grey: among the neighbours of the rounded
value the one that is the closest to the wanted colour and keeps the differences of the channels (the tint) is taken. Run it again after adding a colour.
The Python tools read the palette from the CSS (``tools/palette.py``), so nothing else has to be changed.
"""
import itertools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "mockup" / "src").glob("*.css")) + sorted((ROOT / "mockup" / "src").glob("*.js"))
HEX = re.compile(r"#([0-9a-fA-F]{6})\b")


def expand5(v):
    return (v << 3) | (v >> 2)


def expand6(v):
    return (v << 2) | (v >> 4)


def snap(rgb):
    r, g, b = rgb
    # a dark grey with a hint of blue (#17171a): 565 cannot show a tint that small (a step of blue is 8, of green 4), so it is made a plain grey
    if max(rgb) - min(rgb) <= 6:
        g_ref = (r + g + b) // 3
        r = g = b = g_ref
    base = (round(r * 31 / 255), round(g * 63 / 255), round(b * 31 / 255))
    best, best_cost = None, None
    for dr, dg, db in itertools.product((-1, 0, 1), repeat=3):
        r5, g6, b5 = base[0] + dr, base[1] + dg, base[2] + db
        if not (0 <= r5 <= 31 and 0 <= g6 <= 63 and 0 <= b5 <= 31):
            continue
        p = (expand5(r5), expand6(g6), expand5(b5))
        cost = sum((a - c) ** 2 for a, c in zip(p, rgb)) + 4 * ((p[0] - p[1]) - (r - g)) ** 2 + 4 * ((p[2] - p[1]) - (b - g)) ** 2
        if best_cost is None or cost < best_cost:
            best, best_cost = p, cost
    return best


def main():
    dry = "--dry-run" in sys.argv
    moved = {}
    for path in FILES:
        text = path.read_text(encoding="utf-8")

        def replace(m):
            old = m.group(1).lower()
            rgb = tuple(int(old[i:i + 2], 16) for i in (0, 2, 4))
            new = "%02x%02x%02x" % snap(rgb)
            if new != old:
                moved[old] = new
            return "#" + new

        out = HEX.sub(replace, text)
        if out != text and not dry:
            path.write_text(out, encoding="utf-8")
    for old, new in sorted(moved.items()):
        print("#%s -> #%s" % (old, new))
    print("%d colours %s" % (len(moved), "would change" if dry else "snapped"))


if __name__ == "__main__":
    main()
