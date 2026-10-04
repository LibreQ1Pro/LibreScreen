"""
Global state of the program, split by area: ``g.screen``, ``g.klippy``, ``g.files`` ...

The program started as a port of C++ code that kept everything in global variables. The variables
now live in one object per area (a class below, one instance in this module). The two
connections stay at the top level: ``g.port`` (the screen's serial port) and ``g.ep`` (the
Moonraker websocket).
"""

import queue as _queue

from librescreen.screen.tx import ScreenPort


class Struct(object):
    """Plain struct."""

    def __init__(self, **fields):
        self.__dict__.update(fields)

    def __repr__(self):
        return "Struct(%r)" % self.__dict__


def mks_wifi_status_result_t():
    """The Wi-Fi status as filled from NetworkManager; char arrays become str."""
    return Struct(ack="", bssid="", freq=0, ssid="", id=0, mode="", pairwise_cipher="",
                  group_cipher="", key_mgmt="", wpa_state="", ip_address="", address="", uuid="")


ep = None  # the Moonraker connection (MakerbaseClient)
port = ScreenPort()  # the screen's serial port


class Screen(object):
    """What the screen is showing and the flags of the page logic (which page, keyboards, pending jumps)."""

    def __init__(self):
        self.page = 0  # id of the page currently shown
        self.page_switched_at = 0.0  # when the host switched to it (monotonic): the screen needs a moment
        self.page_mismatch = 0  # how many times in a row the screen said it shows another page
        self.previous_page = 0  # id of the previous page
        self.event_id = 0
        self.page_id = 0
        self.widget_id = 0
        self.type_id = 0
        self.show_preview_complete = False
        self.show_preview_gimage_completed = False
        self.printing_keyboard_enabled = False
        self.auto_level_button_enabled = True
        self.printing_wifi_keyboard_enabled = False
        # NOTE: declared as bool[3] in ui.cpp but indexes 0..4 are used by the code
        # (out of bounds writes in C++).  Five entries are used here.
        self.wifi_ssid_button_enabled = [False, False, False, False, False]
        self.filament_extrude_button = False
        self.temperature_from_main = False        # the temperature keyboard was opened from Home: it returns there
        self.bed_leveling = True
        # 4.4.1 CLL "do not show again" button on the filament confirmation pop-ups
        self.preview_pop_1_on = True
        self.preview_pop_2_on = True
        # 4.4.2 CLL local / USB buttons on the file list page
        self.file_mode = "Local"
        self.manual_count = 0
        self.adjust_mode = "Filament"  # decides which page the "adjust" button opens
        self.set_mode = "Level_mode"  # decides which page the "settings" button opens
        self.load_target = 0
        self.load_mode = False  # True: loading filament, False: unloading
        # 4.4.22 (from the binary)
        self.muted = False  # silent mode: print speed 50%, reset when a print starts
        self.timelapse_enabled = False  # state of Moonraker's timelapse plugin, shown on the preview page
        self.file_list_refreshed = False  # the file list (and its pictures) is up to date: keep the position
        # power off after the print
        self.about_succeeded = False
        self.temp_idle_state = ""
        self.jump_print = False
        self.unhomed_move_mode = 0  # last move button pressed (used when homing is required): 1 x+, 2 x-, 3 y+, 4 y-, 5 z+, 6 z-
        # These flags fix conflicts between the gcode response handler and the refresh
        # functions: the gcode handler only sets a flag and refresh_page_show() changes
        # the page.
        self.jump_move_pop_1 = False
        self.jump_move_pop_2 = False
        self.jump_detect_error = False
        self.jump_level_error = False
        self.jump_filament_pop_1 = False
        self.jump_print_low_temp = False
        self.jump_memory_warning = False
        self.jump_resume_print = False
        self.error_message = ""
        self.main_picture_detected = False  # whether the picture of the cached file exists
        self.main_picture_refreshed = False  # whether the picture on the main page was already refreshed
        self.open_reprint_asked = False  # ask for power loss recovery once after entering the main page
        self.cache_clicked = False


class Klippy(object):
    """The printer as Klipper / Moonraker report it (temperatures, fans, position, print stats, offsets)."""

    def __init__(self):
        self.ready = False
        # 4.4.2 CLL support for the hall effect filament width sensor
        self.filament_detected = True
        # webhooks
        self.webhooks_state = ""
        self.webhooks_state_message = ""
        # gcode_move
        self.gcode_move_speed_factor = 0.0
        self.gcode_move_speed = 0.0
        self.gcode_move_extrude_factor = 0.0
        self.gcode_move_homing_origin = [0.0, 0.0, 0.0, 0.0]  # [X, Y, Z, E] gcode offsets (Z shows babystepping)
        self.gcode_move_gcode_position = [0.0, 0.0, 0.0, 0.0]
        self.toolhead_position = [0.0, 0.0, 0.0, 0.0]
        self.toolhead_axis_minimum = [0.0, 0.0, 0.0, 0.0]
        self.toolhead_axis_maximum = [0.0, 0.0, 0.0, 0.0]
        self.homed_axes = ""                 # the axes Klipper has homed ("xyz"); a position of another axis means nothing
        # x, y, z coordinates
        self.x_position = 0.0
        self.y_position = 0.0
        self.z_position = 0.0
        # gcode z coordinate
        self.gcode_z_position = 0.0
        # extruder
        self.extruder_temperature = 0
        self.extruder_target = 0
        # heater bed
        self.heater_bed_temperature = 0
        self.heater_bed_target = 0
        # chamber ("hot")
        self.hot_temperature = 0
        self.hot_target = 0
        # fan
        self.fan_speed = 0.0
        # heater fan
        self.heater_fan_speed = 0.0
        # heater_fan my_nozzle_fan1
        self.heater_fan_my_nozzle_fan1_speed = 0.0
        # output_pin fan0
        self.out_pin_fan0_value = 0.0
        # output_pin fan2
        self.out_pin_fan2_value = 0.0
        self.out_pin_fan3_value = 0.0
        self.out_pin_beep_value = 0.0
        # idle_timeout
        self.idle_timeout_state = ""
        # print stats
        self.print_stats_filename = ""
        self.print_stats_total_duration = 0.0
        self.print_stats_print_duration = 0.0
        self.print_stats_state = ""  # this state is very useful
        self.display_status_progress = 0
        self.pause_resume_is_paused = False
        self.set_offset = 0.009999999776482582  # float 0.01
        self.z_offset = 0.0
        self.intern_z_offset = 0.0
        self.extern_z_offset = 0.0
        self.move_dist = 10.0
        self.filament_extruder_target = 0
        self.filament_extruder_dist = 50
        # filament switch sensor fila
        self.fila_sensor_detected = False
        self.fila_sensor_enabled = False
        # output_pin caselight
        self.caselight_value = 0.0
        # probe
        self.probe_x_zoffset = 0.0
        self.probe_y_zoffset = 0.0
        self.probe_z_zoffset = 0.0
        # printer info software version
        self.info_software_version = ""
        self.total_print_time = 0.0


class Shown(object):
    """The values last sent to the screen, to resend only what changed."""

    def __init__(self):
        self.extruder_temperature = 0
        self.extruder_target = 0
        self.heater_bed_temperature = 0
        self.heater_bed_target = 0
        self.hot_temperature = 0
        self.hot_target = 0
        self.out_pin_fan0_value = 0.0
        self.out_pin_fan3_value = 0.0
        self.out_pin_fan2_value = 0.0
        self.oobe_enabled = False
        self.page_values = {}       # what the shown page got from the refresh functions; page_to() clears it

    def changed(self, key, value):
        """True when ``value`` is not what the page got last for ``key`` (and remembers it): the refresh runs
        every 50 ms, a page is only written to when something changed."""
        if key in self.page_values and self.page_values[key] == value:
            return False
        self.page_values[key] = value
        return True


class Levelling(object):
    """Bed levelling, z-offset, input shaping and the bed mesh."""

    def __init__(self):
        # levelling while printing
        self.print_extruder_target = 0
        self.print_heater_bed_target = 0
        self.str_manual_level_offset = ""
        # x, y of the 3 screws of the bed screws pages: [bed_screws] screw1..3 of the Klipper config
        self.bed_screws = [(10.0, 10.0), (230.0, 10.0), (125.0, 240.0)]
        # input shaping results
        self.shaper_freq_x = ""
        self.shaper_freq_y = ""
        self.syntony_finished = False
        # levelling
        self.start_pre_auto_level = False
        self.all_level_saving = False
        self.auto_level_heater_bed_target = 0
        # 4.4.2 CLL levelling no longer needs manual z-offset
        self.step_1 = False
        self.step_2 = False
        self.step_3 = False
        self.step_4 = False
        self.bed_offset = 0.0
        # bed_mesh
        self.auto_level_dist = 0.05000000074505806  # float 0.05
        self.auto_level_finished = False
        self.mesh_min = [0.0, 0.0]
        self.mesh_max = [0.0, 0.0]
        self.mesh_points = [[0.0] * 5 for _ in range(5)]
        self.mesh_tension = 0.0
        self.mesh_mesh_x_pps = 0.0
        self.mesh_algo = ""
        self.mesh_min_x = 0.0
        self.mesh_min_y = 0.0
        self.mesh_x_count = 0.0
        self.mesh_y_count = 0.0
        self.mesh_mesh_y_pps = 0.0
        self.mesh_max_x = 0.0
        self.mesh_max_y = 0.0
        # oobe
        self.oobe_printer_set_offset = 0.05000000074505806  # float 0.05
        self.level_list = []


class Files(object):
    """The file list pages, the metadata of the chosen file and the changes Moonraker reports."""

    def __init__(self):
        # file management (std::set<std::string>; kept as Python sets, iterated sorted)
        self.server_list = set()  # gcode file list
        self.server_get_directory = set()  # directories below the path
        self.list_dirname_list = set()
        self.list_filename_list = set()
        self.list_dirname_filename_list = set()
        self.list_modified = {}            # file name -> the time it was added (modified), for the order of the list
        self.list_last_printed = ""        # the file printed last (path under gcodes/), from the history of Moonraker
        self.list_last_printing_files_dir = ""
        self.list_is_last_print_files_dir = False
        # file list page
        self.filelist_changed = False
        self.list_pages = 0
        self.list_current_pages = 0
        self.list_folder_layers = 0
        self.list_list_name = ["", "", "", "", "", "", "", "", ""]  # file names shown in the list
        self.list_list_show_name = ["", "", "", "", "", "", "", "", ""]  # file list names
        self.list_list_show_type = ["[n]", "[n]", "[n]", "[n]", "[n]", "[n]", "[n]", "[n]", "[n]"]  # entry type: [f], [d], [c] or [n]
        self.list_path_stack = []  # path stack (std::stack, top == last element)
        self.list_root_path = ""  # Klippy root directory
        self.list_previous_path = ""  # previous path
        self.list_path = ""  # path of the files
        self.list_print_files_path = ""  # path of the file to print
        self.meta_estimated_time = 0
        self.meta_filename = ""
        self.meta_filament_total = 0.0
        self.meta_object_height = 0
        self.meta_filament_name = ""
        self.meta_filament_type = ""
        self.meta_filament_weight_total = 0.0
        self.meta_gimage = ""
        self.meta_simage = ""
        self.meta_parse_finished = False
        self.thumbnail_relative_path = ""
        self.thumbnail_path = ""
        self.filament_message = ""


class Net(object):
    """Wi-Fi and wired network."""

    def __init__(self):
        self.wifi_ip_address = ""
        # wifi
        self.current_connected_ssid_name = ""
        self.wlan_state_str = ""
        self.lan_connected = False       # the wired interface has a connection (NetworkManager)
        self.status_result = mks_wifi_status_result_t()
        self.ssid_list = []
        self.wifi_ssid_list = ["", "", "", "", ""]
        self.wifi_ssid_list_pages = 0
        self.wifi_current_pages = 0
        self.get_wifi_name = ""


class Config(object):
    """Saved settings (settings.ini) and the files read from the printer configuration."""

    def __init__(self):
        # 800 hours
        self.total_printed_minutes = 0
        # out-of-box experience (first start guide)
        self.oobe_enabled = False
        # mks ini data
        self.fila_status = False
        self.language_status = 2        # the screen's language (index of netstrings), reported by the screen
        self.extruder_target = 0
        self.heater_bed_target = 0
        self.hot_target = 0
        self.serial_by_id = ""


class Update(object):
    """The screen firmware file at start-up, and the answers of the screen to the picture / firmware transfers."""

    def __init__(self):
        self.get_0xfe = False
        self.get_0x06 = False
        self.get_0x05 = False
        self.get_0xfd = False
        self.get_0x04 = False
        self.get_0x24 = False


class Pictures(object):
    """Pictures on their way to the screen."""

    def __init__(self):
        self.input_path = ""
        self.input_size = 0
        # Python only: the ColPic text of the last converted picture.  The original
        # writes it to /home/mks/tjc (gene4.py) and reads the file back; the port keeps
        # it in memory.  None = "the file does not exist" (nothing converted yet).
        self.tjc_data = None
        self.have_64_jpg = [False] * 6
        self.have_64_png_path = [""] * 6
        self.begin_show_64_jpg = False
        self.send_jpg_status = False  # 4.4.22: pictures being sent, refresh_page_show() waits
        self.sent_jpg_to_tjc_start_time = 0  # "static int start_time" inside sent_jpg_to_tjc()


class Rpc(object):
    """The Moonraker message that is being handled."""

    def __init__(self):
        self.message_queue = _queue.Queue()
        self.response_type_id = 0


screen = Screen()
klippy = Klippy()
shown = Shown()
levelling = Levelling()
files = Files()
net = Net()
config = Config()
update = Update()
pictures = Pictures()
rpc = Rpc()
