# Screen mockup

`index.html` — open it in a browser (one file, nothing to install). It shows the design of every page of the screen project (84 pages of
`../project.json`, 90+ views with the states) at 1:1 (272 × 480), with the real texts of the project in the 13 languages: pick the language on
the left, or click "all languages" under a screen to see it in all 13 side by side. A screen that has states (the modes of a keyboard, the
warning of the main page, a long error) has chips under its title: click one to switch. "8 px grid" draws the grid and the page margins, "Widget
names" outlines every widget and the tooltip says `page.widget x,y w×h`: these are the names and rectangles to use in the project.

Rebuild after editing `src/*`: `python3 build_mockup.py` (texts come from `texts.json`, made by `../tools/extract_texts.py` from the pages
and `librescreen/util/netstrings.py`; the page list comes from `../project.json`; the icons are Lucide, ISC license, `icons/*.svg`; the short
captions that belong to the mockup only are in `src/captions.js`). `shot.sh IDS out.png [lang|all] [zoom] [W H] [extra]` takes a screenshot
with google-chrome (`./shot.sh home,file_list /tmp/a.png 2 1 1000 540`; the extra query picks a state: `./shot.sh print_keypad /tmp/a.png 2 1 600 560 '&variant=speed_mute'`;
the window has to be big enough for the page: `all` needs about 1500 × 1700).

## The design in short

* Dark, flat, no gradients or shadows (16-bit colour bands them). Palette: `bg #17171a`, `panel #222226`, `card #2a2a30`, `btn #35353d`, accent `#3d7bff`,
  danger `#e5484d`, heater on `#ff7a59`, text `#f4f4f7` / `#a6a6b3` / `#70707d`.
* One grid of 8 px, page margin 12, content width 248, gap 8. Buttons are 44-52 high (40 minimum), list rows 44-52, keys 44, cards radius 14, buttons 10, keys 8.
* Header 48 (back arrow + title, no bar), navigation bar 56 at y 424 with an accent pill behind the icon of the open page, tabs are a segmented control.
* Primary action = blue (OK, Next, Start), destructive = dark red, disabled = dim. Lists are rows with a chevron / switch / radio / lock / check.
* Pop-ups: dim page, a card with an icon of the kind (info, warning, error, done), the message, one or two buttons at the same place on every pop-up.
* Icons: Lucide line icons (stroke 2); the heaters (nozzle, bed, chamber), the flow and the filament are drawn here.
* Text: units ("°C", "%", "mm") and captions are text, never part of a picture.

## What the screen can do, and what the mockup keeps to

The screen is a TJC4827X243_011 (X2 series): 512 KB of memory, 272 × 480 (the editor says 8 MB of flash, the stock `.tft` is 15 MB, so the real limit is not known). The mockup is drawn within what it can do; `audit.py` checks it.

* **Six fonts.** One size and weight is one font resource (`.zi`), and one multilingual font is about 6 MB, so the screen has: text 13 / 400, 16 / 500, 19 / 600
  and digits 20 / 28 / 32 (all 600; `0-9 . - / % ° ℃ + *`). Nothing on a screen uses another size or weight. The preview font is Noto Sans: the widths, the weights
  and the baseline (`BASE_K` in `src/kit.js`) are provisional until the fonts are rendered, and the size of the finished `.tft` is not known until it is built.
  The shaping of Arabic and Hebrew (joining, right-to-left) is done by the browser here; it is not known whether the screen does it with a plain glyph font,
  so Arabic / Hebrew text has to be tried on the screen (the host can reshape the text, or the strings can be pictures).
* **A text widget cannot change its size at run time** (`x` and `y` can, `w` and `h` cannot). So a value with a unit ("35 %", "220 / 250 °C", "-1.000 mm") is
  several widgets whose widths are constants of the layout (`slot`, `run`, `heatValue`, `pctValue`, `zoffValue`, `coordValue`, `numberInput` in `src/kit.js`): the number is
  aligned to the right and the unit to the left, so the seam between them never moves, and the baselines lie on one line. Temperatures are integers (up to 350), the Z offset has
  three decimals and room for a sign and two digits ("-99.999"), a position of the move page has room for "-999.99". The parts have names (`nozzle_temp`, `nozzle_set`, `nozzle_unit` ...).
* **The text of a name comes from the host** (a file, a SSID): the host cuts it to the slot (`fitName`): at most two lines, the break at `_` `-` space or before the dot, the
  last line ends with "…" and keeps the extension. A message (an error of Klipper) is never cut: it scrolls in its own area (`scrollBox`, the thumb at the right shows there is more).
* **Text from the host is drawn in one font only.** A name of a file or a network, an IP, a message of Klipper can have any character, so the font it uses has to be the wide one (the
  whole of the Unicode that is needed, about 6 MB: the existing `font_title18.zi` has 56 000 glyphs); the other fonts only need the characters of the project's strings. Flash has room for one wide
  font, so every text of the host is text 16 (`DYNAMIC_ROLE` in `src/kit.js`, class `dyn`) and the audit reports a `dyn` text in any other font. That is why the file names are 16 (the
  thumbnails of the list are 104 × 104 to make room) and the network name on the details and "forget" pages is 16, white between muted lines, not a bigger title.
* **The line breaks inside the stock strings** were computed for the old widths by `tools/english_copy.py`; the mockup joins the lines and lets the text flow, and the
  tool makes the final breaks for the real widths.
* **Touch regions** are widgets of their own and at least 40 × 40 (`hit()`): a tab, a slider, a key, a row. The slider is a native slider (`slider()`): a track of 10, a knob of 28 inside a
  touch region of 44; the left end is "off" (fans), so there is no switch.
* **Thumbnails** (file list, print status) are pictures the host makes for the widget: exactly its size, with the rounded corners and the matte of the card already in the pixels (ColPic and
  JPEG have no alpha). The stock project shows the files of the list with `external_picture`, and the vendor warns that this widget does not work on the X2 series: if it fails on the screen,
  the list uses ColPic (`col_pic`, as the print status already does) with the same host-made pictures.
* **The pictures of the platform calibration and of the filament wizards** (`pre_bed_cal`, `bed_calibrate`, the animations) are hand-finished pictures at 4 times the size; `../tools/make_animations.py DIR` scales them down (LANCZOS) to the size of their block, puts the frames of the animations on the block colour with rounded corners (opaque, the screen has no alpha for them) and writes the line art of the calibration pages as transparent pictures into `art/`.
* **Animations:** the frames are the finished ones (`../animations/`), 248 × 192 for the setup guide and 212 × 150 for the wizards.

## States and pages

* Keyboards: `print_kb` (`keybdB`) has the modes of the stock page (nozzle, bed, chamber, speed, flow, three fans; the empty and the filled input; speed has the silent button and
  while it is on the keys are off), `keypad` (`filament_kb`) the three temperatures with the limit written on the stock picture (350 / 120 / 60; the stock page does not clamp the value), `wifi_kb`
  a password (asterisks) or a network name (as typed).
* There is no fans page: the fan tiles of the filament page open the number keyboard, as the fan tiles of the print page do (modes Fan 1-3 of `keypad`).
* `home` has the warning that the UI and the firmware differ; it has no button. `klipper_err`, `detect_error` and `gcode_error` have a long error to show the scrolling area.
* `screen_sleep` (68) is black (backlight 0). The three leftover pages of the old setup guide (`open_video_3`, `open_heaterbed`, `open_calibrate`) have no screen: nothing opens them any more, the audit lists them as not used.
  `internet` (50) is the Wi-Fi page without a network, `open_language2` (78) the second sheet of the first-start language picker.
* Where a state exists (heater on / off, option selected / not, button pressed) the "Components" section and the screens show one state; the others
  follow the same rules (selected = blue radio and raised row; pressed = darker; disabled = dim).

## Checking

`python3 audit.py` draws every screen (and every state) in the 13 languages in headless Chrome and reports: a font that is not one of the six, text that does not fit its widget, a button
whose content overflows, a widget outside the screen, a touch region smaller than 40, a page of `../project.json` without a screen (or twice, or a screen of a page that does not exist; the pages the design does not use any more are listed in `RETIRED_PAGES` of `src/captions.js`: `fila_set_fan` and the three leftovers of the old setup guide), a value that
moves or overflows its slot (with the extreme examples of `src/captions.js`), a name cut wrongly. Widget names longer than 14 characters (the limit the README of the project quotes for the
editor) are listed. It exits with 1 when something fails. `--json` prints the result, `--hw` skips the spacing report; the second part is informational: the gaps other than 8 and the margins other than 12
(`index.html?audit=1`); the back arrow, the items inside a card and the parts of a slider are expected.

What is not checked: the fonts and metrics of the real screen, the size of the `.tft`, the shaping of Arabic / Hebrew, the thumbnails on the screen, the behaviour of the host.

## Names of the pages

The screens and pages carry readable names (`home`, `file_list`, `print_keypad`, `settings`, `klipper_error` ...). `pages.json` is the table
stock page name -> new name (`main` -> `home`, `keybdB` -> `print_keypad` ...) and the old gallery ids -> new ids; `build_mockup.py` checks that it
covers every page of `../project.json` without duplicates. An element has `data-page="new"` and `data-old="stock"`; the texts and the coverage audit
are keyed by the stock name. `?only=`, `shot.sh` and the gallery accept both the new and the old name. `python3 audit.py --names` writes
`names_map.json`: for every stock page the new name, the widgets that stay as in the project (`same`), those the mockup added (`new`, e.g. `*_unit`)
and those that are gone (`gone`). It is the table for porting the host and the screen project.

## Firmware export

`python3 export_spec.py` writes `spec.json` (from `?audit=spec`): every screen and variant, in English and with the texts of the 13 languages, the named widgets (rectangle, kind, font role,
alignment, colour, the label of a button and where it is, the height the text takes) and the ordered fills and icons; `python3 export_layout.py` writes `layout.json` (the same
without the languages; the Home adapter uses it). `?bare=home&static=1` draws one screen at (0,0) with the text, thumbnails and animation content hidden: the pieces
of the screen project are cut from this layer. The names of the widgets are the names in the project (at most 14 bytes). A variant of a screen is not only a state to look at: the
screen project builds a look of a widget from it (`selectable`, `regions` in `../tools/page_rules.py`), so a state the host or the screen switches needs a variant here.

The screen project is made from the mockup by `../tools/migrate_pages.py` and is described in `../README.md`. The pages the design does not draw were removed from the project
(`../tools/renumber.py`), `pages.json` is the table stock name -> readable name of the pages that are left, and `names_map.json` the record of the widgets of the stock pages
against the first export (it is not regenerated: the pages it compares with have been rewritten).
