"""What the engine (migrate_pages.py) cannot read from the mockup: renames, components that go, code that is rewritten by hand.

``RULES[stock page]``: ``aliases`` {new widget: stock widget it inherits the events of}, ``drop`` stock components the new design does not
have, ``keep`` stock components that stay as they are, ``label_names`` {widget: the name of its label}. ``FAMILIES`` are groups of pages
that are migrated together.
"""
import page_patches as patches                    # noqa: E402

POPUP_DROP = ["popup_bg"]

FAMILIES = {
    "popups": ["open_pop", "print_finish", "print_stop", "stop_confirm", "resume_print", "print_no_fil", "print_no_fil2", "print_lowtemp",
               "preview_pop_1", "preview_pop_2", "move_pop_1", "move_pop_2", "filament_pop_1", "unload_finish", "auto_warning", "cal_warning",
               "level_error", "detect_error", "gcode_error", "memory_warning", "restore_config", "update_success", "print_log_s", "print_log_f",
               "wifi_success", "wifi_fail"],
    "busy": ["print_stopping", "re_printing", "syntony_move", "bed_moving", "open_moving", "wifi_connect"],
}

RULES = {name: {"drop": POPUP_DROP} for name in FAMILIES["popups"]}

# -- simple pages
RULES["sys_ok"] = {"drop": ["info_txt"], "actions": {"restart_klip": 2, "restart_fw": 3}}
RULES["bed_finish"] = {"drop": ["z_tilt"]}
RULES["level_mode"] = {"label_names": {"tab_calib": "tab_calib_lbl", "tab_settings": "tab_set_lbl"}}

# -- selectable options: the look of an option that is selected comes from the variant (or the language) of the mockup that selects it
def _language_tiles(names, first):
    return {n: {"off": {"lang": 99}, "on": {"lang": first + i}} for i, n in enumerate(names)}


LANGS1 = ["lang_cn", "lang_ru", "lang_en", "lang_jp", "lang_fr", "lang_de", "lang_it", "lang_es"]
LANGS2 = ["lang_kr", "lang_pt", "lang_ar", "lang_tr", "lang_he"]


def _selected(key):
    return "on"


for _page, _names, _first in (("open_language", LANGS1, 0), ("language", LANGS1, 0), ("open_language2", LANGS2, 8), ("language2", LANGS2, 8)):
    RULES[_page] = {"selectable": _language_tiles(_names, _first), "picture_states": _selected}
RULES["sleep_mode"] = {"selectable": {n: {"off": {"variant": "opt_5min" if n != "opt_5min" else "opt_15min"}, "on": {"variant": n}}
                                      for n in ("opt_5min", "opt_15min", "opt_30min", "opt_never")},
                       "picture_states": _selected, "patch": patches.patch_sleep_mode}

# -- the wizards: the circles and lines of the steps are one picture with a look per step (host: face("steps_bar", state))
def steps(prefix, variants, height=424):
    # The bar is drawn over the page again every time its look changes (a picture that is redrawn covers what lies on it): it must stop above the
    # buttons of the page (the first row starts at y=428), else it wipes the left half of the buttons.
    return {"steps_bar": {"rect": [0, 0, 48, height], "default": prefix + "_0", "states": {"%s_%d" % (prefix, i): v for i, v in enumerate(variants)}}}


SPINNERS = ["spin1", "spin2", "spin3", "spin4"]
for _page in ("filament_pop_2", "filament_pop_3"):
    RULES[_page] = {"regions": steps("load", ["start", "heating", "working", "done"]), "drop": SPINNERS + ["temp_txt"]}
RULES["auto_unload"] = {"regions": steps("unload", ["heating", "unloading", "done"]), "drop": SPINNERS + ["temp_txt"]}
RULES["auto_moving"] = {"regions": steps("level", ["step1", "step2", "step3", "step4"], 480), "drop": SPINNERS + ["bed_lbl"]}

_CSTEPS = {"cstep_001": "d001", "cstep_005": "d005", "cstep_01": "d01", "cstep_05": "d05"}
RULES["pre_bed_cal"] = {"aliases": {"cstep_001": "step_001", "cstep_005": "step_005", "cstep_01": "step_01", "cstep_05": "step_05"},
                        "selectable": {n: {"on": {"variant": v}, "off": {"variant": "d001" if v != "d001" else "d005"}} for n, v in _CSTEPS.items()}}

# -- the lists of networks: the rows and the page buttons have looks (host: face(row, "item" / "check" / "blank"), face(button, "edge" / "more"))
BG = (24, 24, 24)
for _page, _top in (("wifi_list", 104), ("net_saved", 56)):
    _sel = {}
    for _i in range(1, 6):
        _sel["row%d" % _i] = {"item": {"variant": "plain"}, "check": {"variant": "checks"}, "blank": {"blank": BG}}
    _sel["prev_btn"] = {"edge": {"variant": "first"}, "more": {"variant": "plain"}}
    _sel["next_btn"] = {"more": {"variant": "first"}, "edge": {"variant": "checks"}}
    RULES[_page] = {"selectable": _sel, "label_names": {"row%d" % i: "row%d_txt" % i for i in range(1, 6)}}


def _patch_common_set(m):
    """While the setup guide is on, the last row is "Setup Guide": the screen puts its text (kept in the hidden ``guide_txt``) and the normal colour there."""
    timer = next(o for o in m.stock["objects"] if o["attributes"]["objname"] == "sleep_counter")
    lines = timer["events"]["codestimer"]
    at = lines.index("  reset_lbl.txt=guide_txt.txt")
    lines.insert(at + 1, "  reset_lbl.pco=63422")


RULES["common_set"] = {"label_names": {"tab_calib": "tab_calib_lbl", "tab_settings": "tab_set_lbl"}, "keep": ["guide_txt"],
                       "selectable": {"reset_btn": {"oobe_off": {"variant": "reset"}, "oobe_on": {"variant": "guide"}}},
                       "picture_states": lambda key: "oobe_on" if key.endswith("_on") else "oobe_off", "patch": _patch_common_set}


# -- heater editors of the wizards: the whole card switches the heater (the stock ``heat_toggle``); the readout is ``heat_temp`` / ``heat_set`` / ``heat_unit``
RULES["zoffset"] = {"drop": ["cell_%d" % i for i in range(0)]}


# -- the heater icons (host: face("<heater>_icon", "on" / "off")) and the segmented controls (face("<name>", state)) are regions with a look per state
def heat_icon(name, x, y):
    return {name: {"rect": [x, y, 26, 26], "default": "off", "alpha": "ink", "states": {"on": "heat_on", "off": "heat_off"}}}


def segmented(name, rect, states, default=None):
    return {name: {"rect": rect, "default": default or list(states)[1], "states": states}}


_FILAMENT_REGIONS = {}
for _name, _y in (("nozzle_icon", 68), ("bed_icon", 126), ("chamber_icon", 184)):
    _FILAMENT_REGIONS.update(heat_icon(_name, 24, _y))
_FILAMENT_REGIONS.update(segmented("step_seg", [12, 284, 248, 40], {"s10": "seg10", "s50": "seg50", "s100": "seg100"}))
RULES["filament"] = {"regions": _FILAMENT_REGIONS, "drop": ["fan_btn"], "patch": patches.patch_filament,
                     "actions": {"fan1_btn": {"id": 17, "pre": ["sys1=3"]}, "fan2_btn": {"id": 18, "pre": ["sys1=4"]}, "fan3_btn": {"id": 19, "pre": ["sys1=5"]}}}
RULES["move"] = {"patch": patches.patch_move, "regions": segmented("dist_seg", [12, 108, 248, 40], {"d01": "seg01", "d1": "seg1", "d10": "seg10"})}

_OPTIONS = {"pre_heat_temp_opt1_72x70_2": "on", "pre_heat_temp_opt1_press_2_72x70": "on", "pre_heat_temp_opt2_opt1": "on", "pre_heat_temp_opt2_opt1_press_2": "on",
            "pre_heat_temp_opt3_opt1": "on", "pre_heat_temp_opt3_opt1_press_2": "on"}
RULES["pre_heat"] = {"selectable": {"temp_opt%d" % i: {"off": {"variant": "t250" if i == 1 else "t220"}, "on": {"variant": "t%d" % v}}
                                    for i, v in ((1, 220), (2, 250), (3, 300))},
                     "picture_states": lambda key: _OPTIONS.get(key, "off")}
RULES["bed_calibrate"] = {"drop": ["screw_pic"]}


def _patch_load_heat(m):
    """The next button of "Load filament: heat" waits for the temperature: the screen refuses the tap itself (the number variables the host
    keeps: ``cur_val`` = the nozzle temperature, ``tar_val`` = the target); the host also dims the button and switches its touch off."""
    nxt = next(o for o in m.stock["objects"] if o["attributes"]["objname"] == "next")
    nxt["events"]["codesup"] = ["tmp_val.val=cur_val.val+10", "if(tar_val.val>0&&tmp_val.val>=tar_val.val&&tmp_val.val>=185)", "{",
                                "  prints 0x65,1", "  prints dp,1", "  prints 2,1", "  prints 0xff,1", "  prints 0xff,1", "  prints 0xff,1", "}"]
    from gen_project import variable
    for name in ("tar_val", "tmp_val"):
        m.stock["objects"].append(variable(name, sta=0, val=0))


RULES["filamentVideo2"] = {"drop": ["temp_now", "temp_target"], "patch": _patch_load_heat,
                           "regions": heat_icon("nozzle_icon", 24, 64),
                           "selectable": {"next": {"wait": {"variant": "heating"}, "ready": {"variant": "ready"}}}}
RULES["auto_heaterbed"] = {"drop": ["temp_now", "temp_target"], "regions": heat_icon("bed_icon", 24, 68)}


RULES["filament_kb"] = {"drop": ["input_bg"], "patch": patches.patch_filament_kb}


_KEYS = ["key_%d" % i for i in range(10)] + ["key_del", "key_ok"]


def _keybdb_states(key):
    if key.startswith("keybdB_mute"):
        return "on" if key.startswith("keybdB_mute_on") else "off"
    return "off" if key.endswith("_kb_mute_on") else "on"


RULES["keybdB"] = {"drop": ["pct_sign"], "patch": patches.patch_keybdB, "picture_states": _keybdb_states,
                   "selectable": {**{k: {"on": {"variant": "nozzle"}, "off": {"variant": "speed_mute"}} for k in _KEYS},
                                  "mute_btn": {"off": {"variant": "speed"}, "on": {"variant": "speed_mute"}}}}


# -- the print pages
_ROWS = {}
for _name, _y in (("nozzle_icon", 238), ("bed_icon", 304), ("chamber_icon", 370)):
    _ROWS.update(heat_icon(_name, 24, _y))
RULES["printing"] = {"drop": ["pct_sign"], "regions": _ROWS}
RULES["printing_2"] = {"drop": ["pct_sign"], "aliases": {"light2_btn": "light_btn"}, "patch": patches.patch_printing_2,
                       "selectable": {"light2_btn": {"off": {"variant": "light_off"}, "on": {"variant": "normal"}}}}
RULES["print_filament"] = {"drop": ["pct_sign"], "aliases": {"nozzle_temp": "temp_now", "nozzle_set": "temp_set"}, "regions": heat_icon("nozzle_icon", 24, 278)}
_ZS = {"step_001": "zs001", "step_005": "zs005", "step_01": "zs01", "step_05": "zs05"}
RULES["print_zoffset"] = {"drop": ["pct_sign"],
                          "selectable": {n: {"z_off": {"variant": "zs001" if v != "zs001" else "zs005"}, "z_on": {"variant": v}} for n, v in _ZS.items()}}


# -- the file list: the slots, the tabs and the three buttons have looks (host: face(slot, "file" / "dir" / "none"), face("tabs_seg", "local" / "usb"), face(button, "on" / "off"))
_SLOTS = {"file%d" % i: {"none": {"variant": "none"}, "file": {"variant": "mixed"}, "dir": {"variant": "dirs"}} for i in range(1, 5)}
RULES["filelist"] = {"keep": ["empty_msg"], "drop": ["file1_mark"], "patch": patches.patch_filelist, "picture_states": lambda key: "none",
                     "regions": {**segmented("tabs_seg", [12, 8, 248, 40], {"local": "mixed", "usb": "tab_usb"}, "local")},
                     "selectable": {**_SLOTS,
                                    "prev": {"off": {"variant": "mixed"}, "on": {"variant": "nav_on"}},
                                    "next": {"on": {"variant": "mixed"}, "off": {"variant": "nav_off"}},
                                    "up_dir": {"on": {"variant": "mixed"}, "off": {"variant": "nav_off"}}}}

RULES["net_detail"] = {"selectable": {"auto_btn": {"off": {"variant": "auto_off"}, "on": {"variant": "auto_on"}}}}
RULES["net_info"] = {"drop": ["wifi_txt", "lan_txt"], "selectable": {"radio_btn": {"off": {"variant": "none"}, "on": {"variant": "wifi"}}}, "actions": {"wifi_btn": 2}}

RULES["preview"] = {"aliases": {"file_name": "err_msg"}, "keep": ["cp_data", "cp_pad"], "patch": patches.patch_preview,
                    "selectable": {"level_btn": {"off": {"variant": "both_off"}, "on": {"variant": "default"}},
                                   "timelapse_btn": {"off": {"variant": "default"}, "on": {"variant": "both_on"}}}}


_WIFI_KB = {"wifi_kb_key_shift": "lower", "wifi_kb_key_shift_press": "lower", "wifi_kb_key_shift_off": "upper", "wifi_kb_key_shift_press_42x67": "upper",
            "wifi_kb_key_shift_sym_page": "sym", "wifi_kb_key_sym_press": "sym", "wifi_kb_key_ok": "on", "wifi_kb_key_ok_press": "dim"}
RULES["wifi_kb"] = {"keep": ["refresh_show"], "patch": patches.patch_wifi_kb, "picture_states": _WIFI_KB,
                    "selectable": {"key_shift": {"lower": {"variant": "password"}, "upper": {"variant": "upper"}, "sym": {"variant": "sym"}},
                                   "key_ok": {"on": {"variant": "password"}, "dim": {"variant": "ok_dim"}}}}

# -- translations that do not fit their slot in the font of the screen (found by tools/test_pages.py): {widget: {language: text}}
_JA_CALIB = {"tab_calib": {3: "キャリブ"}}
RULES["common_set"]["overrides"] = _JA_CALIB
RULES["level_mode"]["overrides"] = _JA_CALIB
RULES["wifi_kb"]["overrides"] = {"title": {7: "Contraseña"}}
