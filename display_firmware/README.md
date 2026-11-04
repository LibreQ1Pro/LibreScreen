# Screen firmware (TJC / USART HMI, 272x480)

The unpacked stock V4.4.24 project in the portable format, plus the network management pages made for the Python librescreen
(`librescreen/pages/connections.py`, `librescreen/system/network.py`). Compatibility with QIDI's xindi is not kept.

## The screen project follows the mockup

Every page of the project (84 pages) is made from the design in `mockup/` (see `mockup/README.md`); the behaviour of a page is the one of the stock
project: the same actions reach the host (`tools/test_behaviour.py` touches every component that both projects have and compares the frames).
The pages the new design does not use (`open_video_3`, `open_heaterbed`, `open_calibrate`, `fila_set_fan`, `internet_page`: Settings > Network opens the network info) and the stock fonts (`font_title18`,
`font_small14`, `font_digits24`), the blinking step animations and every picture no page refers to are gone; the numbers of the pages are the positions in
`project.json`, so `librescreen/screen/pageids.py`, the numbers in the code of the pages and the traces of `tests/e2e/golden` moved with them
(`tools/renumber.py`).

### Names and order of the pages

The pages of the project have readable names (at most 14 characters, the limit of the editor) and are in the order of using the printer: boot, setup guide, home, filament, move,
files, printing, calibration, settings, network, errors. The table is `mockup/pages.json` (`pages`: stock name -> the name of the mockup, `short`: the name of the mockup -> the
name in the project where it is longer than 14 characters, `order`); `tools/page_names.py` reads it and `tools/rename_pages.py` applies a change of it (names, order, the page
numbers in the code and in `librescreen/screen/pageids.py`). The tools keep the stock names as the *source* names (`tools/migration_sources/`, `tools/migrated.json`, the rules).

### The number keyboard of the print pages

`print_keypad` is a page like the others: a value of a print page (nozzle, bed, chamber, speed, flow, fans) opens it with its own touch event
(`tools/page_patches.py` `explicit_keypad`: it sets `print_keypad.loadpageid` to the page to return to and does `page print_keypad`). The stock binds
those values to the editor's system keyboard (`key=2`, a page that must be called `keybdB` and cannot be renamed); nothing in the project is bound that way any more.

### How a page is made

```bash
python3 mockup/build_mockup.py && python3 mockup/export_spec.py      # the design -> mockup/spec.json (every screen and variant, 13 languages)
python3 tools/make_fonts.py                                          # the six fonts (.zi)
python3 tools/make_spinner.py                                        # the frames of the loading spinner (animations/spinner)
python3 tools/migrate_pages.py --all                                 # the pages (tools/page_rules.py: what the engine cannot read from the design)
python3 tools/gen_project.py boot_logo restart_needed shutting_down  # the three plain pages
python3 tools/migrate_home.py                                        # Home (its own adapter)
python3 tools/prune_resources.py                                     # what no page uses any more goes
python3 tools/build_hmi.py out/display.HMI                           # lints, validate, pack, parse check
```

`tools/migrate_pages.py` (read its docstring) draws a page from the static rendering of the design (`index.html?bare=ID&static=1`, no run-time text): a card or a
panel is a `picture` that is a crop of it (the corners hold what lies under them, so no alpha is needed); a button, a key, a row or a navigation item is a
`button` with a released and a pressed tile (the pressed one is the released one darkened inside its rounded shape; a button that has a host-written text or a picture on top of it keeps its look when pressed, and the title bar, a button without a fill, gets a little lighter); a touch region is a `touch_hotspot`;
a label is the `txt` of a centred button or a `text` of its own that forwards the touch; a text is a `text` with the font of its role, as tall as its longest
translation needs (the glyph widths of the real fonts are used), transparent when the page writes it once, solid (it erases the old text) when the host
changes it. A component that the stock page has keeps its events by name (`aliases` of the rules map a new name to a stock one). What the engine cannot decide it
refuses: a stock component the design does not draw must be named in the rules (`drop` / `keep`), a line of code that names a component the page lost is an error,
a picture of the stock design used by the code must be said what it stands for (`picture_states` of a `selectable` widget). The pages are written from the saved
sources in `tools/migration_sources/` (the stock pages) and `tools/migrated.json` records the hash of what was written: the generator refuses a page that was edited
by hand, so port a change to the rules or the adapters (`tools/page_patches.py`: the value keyboards, the Wi-Fi keyboard, the print pages) instead.

The screen breaks a long text at the last letter that fits, not at a space: `break_lines` of `migrate_pages.py` puts the line breaks (`\r`) at the spaces, for the real
glyph widths and the width of the widget, into the text of the page and into the chain of translations. A text of the host is cut by `librescreen/screen/text.py`.

States of a widget are looks of one picture or one widget that the screen or the host switches: a widget can be `selectable` (a look per variant or language of the
mockup that shows it: the language tiles, the options of the sleep time, the steps of a distance), a `region` of the page can have a look per variant (the steps of a
wizard `steps_bar`, the heater icons `nozzle_icon` ..., the segmented controls `step_seg`, `dist_seg`, `tabs_seg`). The host asks for a look with `g.port.face(widget, state)`
(`tools/faces.json`, `librescreen/screen/faces.py`).

### The fonts

Six fonts, one size and weight each (`tools/make_fonts.py`, Noto Sans; Arabic and Hebrew from their Noto faces, kana, ideographs and hangul from Noto Sans CJK):
text 13 / 400, 16 / 500, 19 / 600 and digits 20 / 28 / 32 (all with `-`, a value the host has not sent shows `---`). Text 16 is the one wide font (46 056 glyphs): every text
that comes from the host (names of files, networks, messages) is drawn in it; `librescreen/screen/font_t16.widths` has its advances, the host cuts a name to its slot with them
(`librescreen/screen/text.py`). The characters of the strings of the project and of the text the screen sets itself (`.txt="..."` in event code) are in the other fonts.
The cell of text 13 / 16 / 19 is 18 / 20 / 26 px, of the digits 28 / 40 / 46; a text box is never shorter than the lines of its longest translation need.
Arabic and Hebrew are single glyphs without joining and right-to-left layout (the browser of the mockup does both): that has to be tried on the screen.
A scrolling text (type 55) has no layout in the portable project, so a long error message is a wrapped text that the host cuts to what fits.

### The pictures that the host makes

Thumbnails are exactly the size of their widget with the colour of their card and the round corners in the pixels (ColPic and JPEG have no alpha):
Home 140 (ColPic), the file list slots 104 (JPEG through `external_picture`), the preview 152, the print pages 132 and their number keyboard 72 (two ColPic texts
`cp_data`, `cp_data_s` that the preview page holds), see `librescreen/screen/thumbnail.py` (`prepare_picture`) and `librescreen/pages/preview.py`.

### Checks

From this directory (they need hmi-builder; `test_behaviour.py` also the git history for the stock project):

```bash
python3 tools/test_pages.py          # every page in 13 languages in the emulator: no error of the screen, every glyph exists, every text fits its widget
python3 tools/test_behaviour.py      # the same frames reach the host as with the stock project (page numbers compared by name)
python3 tools/check_host_names.py    # every widget the host writes to exists on some page
python3 tools/lint_faces.py          # the looks of the host exist and are as big as their widget
python3 mockup/audit.py --hw         # what the screen could not show, in the mockup
```

and from `src_py/`, in docker or on the printer, never on the development host: `python3 -m unittest discover -s tests/unit`,
`display_firmware/tools/test_new_design.py` (the Home page with the host, in the emulator) and `python3 tests/e2e/golden.py check -j 22`.
`tools/render_pages.py out/sheet.png page ...` draws pages of the project in the emulator next to the mockup.

### Not verified on the real screen

The alpha-free tiles and the transparent texts over pictures; the native slider with `ch` / `dis` (round track and cursor; the emulator draws a full bar);
the `external_picture` thumbnails of the file list on this screen model; the ColPic thumbnails at the new sizes; Arabic and Hebrew; the flash size of the `.tft`
(the compiled pictures are about 0.4 MB, the fonts 7.5 MB, the animation frames 0.9 MB as PNG; the stock `.tft` is 15.2 MB); the speed of redrawing a page with
many components. The About row of the settings page has no page behind it yet; the preheat page offers 220 / 250 / 300 only (no custom temperature).

## Build

The project is built with [hmi-builder](../../../QSART_Linux_EN/hmi-builder) (`pip install Pillow fonttools`):

```bash
python3 tools/build_hmi.py [OUT.HMI]     # default: out/display.HMI
```

It runs the four lints (`lint_program`, `lint_frames`, `lint_page_ids`, `lint_faces`), `validate`, `pack`, `hmi_parse --check`
and writes `OUT.HMI.sha256`. hmi-builder is found through `$HMI_BUILDER` (its checkout), then `../../hmi-builder`,
then `~/Projects/QSART_Linux_EN/hmi-builder`. `.github/workflows/display.yml` runs the lints and the `ponywka/hmi-builder` action in CI and uploads the
`.HMI` as an artifact.

`OUT.HMI` is a project, not the firmware: open it in USART HMI and use *File -> Output production file* to get the
`.tft` (the printer flashes `/root/800_480.tft` into the screen at start-up).

`tools/add_network_pages.py` is the script that made the network changes from the stock sources (it refuses to run
twice); `tools/draw_source_switch.py` redraws the LAN / Wi-Fi switch of the network page as a two-segment control with Lucide icons (`icons/`, ISC license);
`tools/draw_network_pictures.py` draws the backgrounds of the network pages (antialiased rounded corners, run it
again after changing a layout). Helpers: `tools/page_dump.py` (a page as text), `tools/pic_sheet.py` (pictures by id on one
image), `tools/name_pictures.py` (how the picture names were proposed); on the printer, `tests/printer/check_network.py`
checks the NetworkManager part of librescreen. `tools/preview_page.py OUT.png page...` draws a rough preview of pages (Noto Sans instead of the screen fonts).

## Settings kept in the screen's EEPROM

| address | variable | set by |
|---|---|---|
| 100 | `lang` | the language pages (`wepo lang,100`) |
| 200 | `sleep_time` | the screen sleep page |
| 300 | `max_dim` (brightness 10..100) | the slider of the screen sleep page (`tools/add_brightness.py` built it): moving it sets `max_dim` and `dim` at once, releasing it writes the EEPROM; `Program.s` applies it at power-up and the pages restore it with `dim=max_dim` |

`Program.s` repairs a value out of range (an erased EEPROM reads -1).

## Languages

The language is stored in one place, the screen: `lang` lives in its EEPROM (address 100, `Program.s` reads it, the language pages
write it with `wepo`). The host keeps no copy on disk (`settings.ini` has no language): it asks for the value at
start-up and when the screen powers up (`prints 0xa0,1`, `prints lang,1`, terminator) and the language buttons report every change
with the frame `a0 lang ff ff ff`; the host only caches the number to pick the texts it sends itself (`util/netstrings.py`).

The screen has 13 languages (the global `lang`: 0 zh, 1 ru, 2 en, 3 ja, 4 fr, 5 de, 6 it, 7 es, 8 ko, 9 pt, 10 ar, 11 tr,
12 he); every page sets its texts in `codesload` with an `if(lang==N)` chain. The text stored in the component itself
(what the editor shows) is English. No picture has text drawn in (the stock firmware had per-language pictures `*_cn`, `*_en`, `*_ru` ...
for the fan names, the language buttons, the restart buttons and the shutdown / restart / boot pages): the texts are components with the
`if(lang==N)` chain of `codesload`, so they can be edited in the editor and translated like every other text. Rules for new texts:

- put the English text into the `txt` attribute, translations into `codesload`; a component whose text comes from the host at run time (the network pages: names, addresses, states) is left
  empty, so nothing wrong flashes while the page loads (`tools/preview_page.py` has its own sample data to draw them);
- `txt_maxl` is in bytes: a Chinese character takes 3, an Arabic one 2; check the longest language;
- the network pages take their texts from `librescreen/util/netstrings.py` (the host uses the same table for the texts that depend on
  the state): edit the table, then run `python3 tools/net_i18n.py` from this directory;
- the translations of a page are the ones of the stock page (`tools/migration_sources/<page>.json`, written by `tools/english_copy.py` / `tools/translations.py` before the pages
  were generated) and, for a text that the new design added, the ones of the mockup (`mockup/texts.json`, `mockup/src/captions.js`). `tools/test_pages.py` reports a text
  that is wider or taller than its widget in any language; a translation that does not fit is replaced in the rules (`overrides` of `tools/page_rules.py`);
- `tools/lint_program.py` checks `Program.s`: every global is used by a page or the host and none is declared twice;
- `tools/page_context.py` prints every page next to the buttons it really has (to check that "tap Next" refers to a button that exists; buttons named in a text are put in quotes, an icon button is written as the icon: “>”, “+”, “↓”);

## Frames to the host

Everything the screen sends is a frame that ends with `ff ff ff`. The editor adds it by itself to the keys of
"send key" components and to `get` / `sendme`, but `prints` and `printh` send exactly what they are told: every handler
that prints a frame has to print the terminator itself (three `prints 0xff,1`, or `printh ... ff ff ff`). The host
(`librescreen/screen/rx.py`) cuts the stream at the terminators, so a frame without one is glued to the next frame and both are
lost. `python3 tools/lint_frames.py` finds such handlers (`--fix` adds the terminators); run it after every change of
an event. Some frames carry a page id written as a number (the sleep timer, the language pages, the value
keyboards); the host compares it with `librescreen/screen/pageids.py`, so `python3 tools/lint_page_ids.py` has to be run
whenever pages are added or removed. Frames the host knows: `65 page widget [event]` (click), `70 mode row text` (keyboard), `71 page widget low high`
(a number, 2 bytes, may be `ff ff`), `1a` (invalid variable name), `91` (the screen was updated). The only thing without
a terminator is the single byte `05` the screen answers to every data packet of a picture transfer.

## Network pages

| page | what | actions sent as `65 <page id> <action> ff ff ff` |
|---|---|---|
| `wifi_list` | scan list (a known network opens its `net_detail` page: connect, new password, forget; a new one asks for the password); buttons "Saved" / "Hidden" next to refresh | rows 0-4, 5 prev, 6 next, 7 refresh, 8 saved, 9 hidden, 23 back to the network info |
| `net_saved` | saved Wi-Fi connections, 5 rows with paging | rows 0-4, 5 prev, 6 next, 23 back |
| `net_detail` | one connection | 1 connect / disconnect, 2 new password, 3 autoconnect, 4 forget, 23 back |
| `net_confirm` | forget the connection? | 1 forget, 0 cancel, 23 back |
| `net_info` | the first page of Settings > Network: the Wi-Fi and LAN interfaces (name, SSID, IP, GW; `---` when not known) | 1 Wi-Fi radio on/off, 2 the list of Wi-Fi networks, 23 back to the settings (the wired link is never switched) |
| `wifi_kb` | the keyboard, now with a mode | 0 back; the text is sent as `0x70 <kbmode> <row> <text>` |

Texts of the new pages: English and Russian (Russian when `lang==1`, English for every other language).

The host sets the globals `kbmode` (1 password of a scanned network, 2 new password of a saved one, 3 hidden SSID,
4 hidden password) and `kbmin` (shortest accepted text) before it opens `wifi_kb`.

## Names

Components, pictures, fonts and animations have readable names (the stock project used `b0`, `t1`, `pic_25`, `anim_3`).
`tools/names.json` maps the stock names to the current ones, page by page; `tools/rename_objects.py` applied it (it
rewrites the names and every reference in event code, checks the result, and verifies that the inverse renaming gives
the original project back; the compiled pages differ from the stock ones only in the names). The names the Python librescreen
writes in instructions were changed with `tools/rename_host.py` (`--verify` re-checks that every name the host uses
exists on the page it addresses).

Conventions (names are at most 14 characters, the editor's limit):

| name | what |
|---|---|
| `back_btn`, `title` | the header: the (invisible) back button and the title text |
| `nav_main`, `nav_adjust`, `nav_files`, `nav_settings` | the navigation bar at the bottom |
| `msg`, `ok`, `cancel`, `popup_bg` | message pages and pop-ups |
| `next_btn`, `prev_btn`, `next`, `prev` | paging / wizard buttons |
| `key_0`..`key_9`, `key_a`..`key_z`, `key_ok`, `key_del`, `key_space` | keyboards |
| `nozzle_*`, `bed_*`, `chamber_*`, `fan1_*`..`fan3_*` | heaters and fans: `_btn` / `_row` / `_toggle` the buttons, `_temp` the current value, `_set` the target |
| `time_elapsed`, `time_left`, `progress`, `progress_pct`, `file_name`, `thumb` | the print status block of the printing pages |
| `row1`..`row5` (`row1_txt`) | list rows of the Wi-Fi and saved-network lists; `file1`..`file4` (`file1_name`, `file1_pic`) on the file list |
| `spin1`..`spin4`, `steps_bar`, `step1_txt`.. | the step indicator of the wizards |
| `lang_cn`, `lang_ru`, ... | language buttons (the order is the value of the screen's `lang`) |

## Pictures

A page is a flat colour with pictures on it: **decor** (a crop of the design: a card, a panel, a pill, an icon, art; `new_decor_<w>x<h>_<hash>`), the **faces** of the buttons
(`new_<widget>_<w>x<h>_<hash>` released and `..._press`) and the **looks** the screen or the host switches (`new_<widget>_<state>_...`). A tile has the size of its widget and the colour
that lies under its corners in the pixels, so it needs no alpha; equal tiles are one picture (the name has the hash of the pixels). The pictures of the stock design that
pages still show are the animations of the setup guide (`animations/`, made by `tools/make_animations.py` from the hand-finished 4x pictures), the art of the calibration pages (`tools/make_animations.py`) and the boot logo (the LibreQ1Pro mark: `tools/make_boot_logo.py` draws `mockup/art/LibreQ1Pro.svg` onto `pictures/boot_logo.png`). The stock
tile tools (`tools/tile_*.py`, `tools/pictures.py`, `tools/unbake_*.py`, `tools/add_brightness.py`) and `tools/names.json` are the record of how the stock project was prepared; the
resources they mention are gone.

**Looks of the host.** The host (librescreen/pages) does not send picture ids by name: `g.port.face("nozzle_icon", "on")` sends `nozzle_icon.pic=<tile>` and `nozzle_icon.pic2=<tile>` of that
state. `tools/faces.json` lists the tiles of every `widget -> state`; `tools/gen_faces.py` writes `librescreen/screen/faces.py` from it and the position of the pictures,
`tools/lint_faces.py` (part of `build_hmi.py`) checks that the tiles exist and are as big as the widget, `tests/unit/test_faces.py` finds a `face()` of the host that asks for
a look that is not in the table. `tools/prune_resources.py` removes what nothing refers to (it writes `faces.py` again: the id of a picture is its position).
