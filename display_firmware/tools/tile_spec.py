"""The looks a widget gets from the host while the screen runs: (page, name of the group of tiles, widgets, states).

A state is ``(sheet shown released, sheet shown pressed or None)``: the stock sheets that the host (librescreen/pages) put
into ``<widget>.picc`` / ``<widget>.picc2``. tile_pictures.py turns every state into tiles and writes
librescreen/screen/faces.py: ``g.port.face(widget, state)`` sends the two tiles. A widget and a state name identify the tiles,
so two pages that use the same widget name with different looks need different state names.
"""

SPEC = [
    # filament: the heater rows of the page, the extrusion step
    ("filament", "toggle", ["nozzle_toggle", "bed_toggle", "chamber_toggle"],
     {"on": ("filament_row_on", "filament_press_on"), "off": ("filament_row_off", "filament_press_off")}),
    ("filament", "row", ["nozzle_row", "bed_row", "chamber_row"],
     {"on": ("filament_row_on", "filament_press_on"), "off": ("filament_row_off", "filament_press_off")}),
    ("filament", "step", ["step_10", "step_50", "step_100"],
     {"on": ("filament_row_on", "filament_press_on"), "off": ("filament_row_off", "filament_press_off")}),
    ("fila_set_fan", "toggle", ["fan1_toggle", "fan2_toggle", "fan3_toggle"],
     {"on": ("fan_row_on", "fan_press_on"), "off": ("fan_row_off", "fan_press_off")}),

    # the step indicator of the wizards
    ("filament_pop_2", "steps", ["steps_bar"],
     {"load_1": ("pop_steps_1", None), "load_2": ("pop_steps_2", None), "load_3": ("pop_steps_3", None)}),
    ("filament_pop_3", "steps", ["steps_bar"],
     {"load_1": ("pop_steps_1", None), "load_2": ("pop_steps_2", None), "load_3": ("pop_steps_3", None)}),
    ("auto_unload", "steps", ["steps_bar"],
     {"unload_1": ("unload_steps_1", None), "unload_2": ("unload_steps_2", None)}),
    ("auto_moving", "steps", ["steps_bar"],
     {"level_1": ("auto_steps_1", None), "level_2": ("auto_steps_2", None), "level_3": ("auto_steps_3", None)}),

    # the main page
    ("main", "heater", ["nozzle_btn", "bed_btn", "chamber_btn"],
     {"on": ("main_on", "main_on_press"), "off": ("main_off", "nav_btn_press")}),
    ("main", "switch", ["light_btn", "beep_btn"],
     {"on": ("main_on", "main_on_press"), "off": ("main_off", "nav_btn_press")}),
    ("main", "last_file", ["last_file_btn"],
     {"noimg": ("main_bg_noimg", "main_on_press"), "photo": ("main_bg_photo", "nav_btn_press")}),
    ("main", "icon", ["lan_icon", "usb_icon", "wifi_icon"], {"on": ("main_on", None), "off": ("main_off", None)}),

    # printing
    ("printing", "heater", ["nozzle_btn", "bed_btn", "chamber_btn"],
     {"heat_on": ("printing_row_on", "printing_press_on"), "heat_off": ("printing_row_off", "printing_press_off")}),
    ("printing_2", "light", ["light_btn"],
     {"lamp_on": ("light_on", "printing2_press_on"), "lamp_off": ("light_off", "printing2_press_off")}),
    ("print_filament", "heat", ["heat_btn"],
     {"on": ("printfil_heat_on", "printfil_press_on"), "off": ("printfil_heat_off", "printfil_press_off")}),
    ("print_zoffset", "step", ["step_001", "step_005", "step_01", "step_05"],
     {"z_on": ("zoffset_step_on", "zoffset_step_press_on"), "z_off": ("zoffset_step_off", "zoffset_step_press_off")}),
    ("pre_bed_cal", "step", ["step_001", "step_005", "step_01", "step_05"],
     {"on": ("prebed_step_on", "prebed_press_on"), "off": ("prebed_step_off", "prebed_press_off")}),
    ("keybdB", "mute", ["mute_btn"],
     {"off": ("kb_mute_off", "kb_mute_off_press"), "on": ("kb_mute_on", "kb_mute_on_press")}),
    ("preview", "check", ["level_btn", "timelapse_btn"],
     {"on": ("preview_chk_on", "preview_press_on"), "off": ("preview_chk_off", "preview_press_off")}),

    # heating on the leveling and guide pages
    ("auto_heaterbed", "heat", ["heat_toggle"],
     {"bed_on": ("autobed_on", "autobed_press_on"), "bed_off": ("autobed_off", "autobed_press_off")}),
    ("filamentVideo2", "heat", ["heat_toggle"],
     {"guide_on": ("open_heat_on", "open_heat_on_press"), "guide_off": ("open_heat_off", "open_heat_off_press")}),

    ("move", "distance", ["dist_01", "dist_1", "dist_10"],
     {"on": ("move_dist_on", "move_dist_on_press"), "off": ("move_dist_off", "move_dist_off_press")}),

    # lists of the network pages
    ("wifi_list", "row", ["row1", "row2", "row3", "row4", "row5"],
     {"check": ("rows_check", "rows_check_press"), "item": ("rows_lock", "bg_settings_press"),
      "blank": ("bg_settings_panel", "bg_settings_panel")}),
    ("net_saved", "row", ["row1", "row2", "row3", "row4", "row5"],
     {"check": ("rows_check", "rows_check_press"), "item": ("rows_lock", "bg_settings_press"),
      "blank": ("bg_settings_panel", "bg_settings_panel")}),
    ("wifi_list", "page", ["prev_btn", "next_btn"],
     {"edge": ("rows_check", "bg_settings_press"), "more": ("rows_lock", "rows_check_press")}),
    ("net_saved", "page", ["prev_btn", "next_btn"],
     {"edge": ("rows_check", "bg_settings_press"), "more": ("rows_lock", "rows_check_press")}),
    ("internet_page", "source", ["source_switch"],
     {"wired": ("ip_switch_on", "ip_press_on"), "wifi": ("ip_switch_off", "ip_press_off")}),
    ("common_set", "reset", ["reset_btn"],
     {"oobe_on": ("reset_row_on", "settings_press_on"), "oobe_off": ("reset_row", "settings_press")}),

    # the file list
    ("filelist", "entry", ["file1", "file2", "file3", "file4"],
     {"file": ("files_item_img", "files_tab_local_press"), "dir": ("files_item_dir", "files_dir_press"),
      "none": ("files_tab_usb", "files_tab_usb")}),
    ("filelist", "tab", ["local_tab", "usb_tab"],
     {"local": ("files_tab_local", "files_tab_local_press"), "usb": ("files_tab_usb", "files_tab_usb_press")}),
    ("filelist", "arrow", ["prev", "next", "up_dir"],
     {"off": ("files_item_img", "files_dir_press"), "on": ("files_item_dir", "files_tab_local_press")}),
]
