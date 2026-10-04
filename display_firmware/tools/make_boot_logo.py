#!/usr/bin/env python3
"""The boot logo: the LibreQ1Pro mark (mockup/art/LibreQ1Pro.svg) on the colour of the page.

    python3 tools/make_boot_logo.py            (run from display_firmware/)

Writes mockup/art/logo.png (the mark, 160 x 160, the mockup shows it) and pictures/boot_logo.png (the whole 272 x 480 page of the boot logo: the mark on the
page colour, opaque; the text of the page lies under it). The svg is drawn by Chrome (it is the renderer of the mockup too).
"""
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIZE = 160
AT = (56, 100)          # the mark is in the middle of the page, above the message (y 330)
CSS = (ROOT / "mockup" / "src" / "style.css").read_text(encoding="utf-8")


def page_colour():
    m = re.search(r"--bg:#([0-9a-fA-F]{6})", CSS)
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))


def main():
    svg = ROOT / "mockup" / "art" / "LibreQ1Pro.svg"
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "logo.html"
        # the svg has a rounded square in the colour of the page behind the mark: left out, its anti-aliased edge (23, 25, 26, 27 instead of 24) shows as faint arcs
        # at the four corners of the mark (the screen blends it with the page again)
        plain = Path(tmp) / "mark.svg"
        plain.write_text(re.sub(r"\s*<rect [^>]*/>", "", svg.read_text(encoding="utf-8")), encoding="utf-8")
        html.write_text('<body style="margin:0;background:transparent"><img src="%s" width="%d" height="%d" style="display:block"></body>' % (plain.as_uri(), SIZE, SIZE))
        shot = Path(tmp) / "logo.png"
        subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1", "--default-background-color=00000000",
                        "--window-size=%d,%d" % (SIZE, SIZE), "--screenshot=" + str(shot), html.as_uri()], capture_output=True, timeout=120, check=True)
        mark = Image.open(shot).convert("RGBA")
    mark.save(ROOT / "mockup" / "art" / "logo.png")
    page = Image.new("RGB", (272, 480), page_colour())
    page.paste(mark, AT, mark)
    page.save(ROOT / "pictures" / "boot_logo.png")
    print("boot_logo", page.size)


if __name__ == "__main__":
    main()
