"""Handling of the "notify_gcode_response" messages of Moonraker."""

import logging
import re
import time

from librescreen import state as g
from librescreen.screen import navigation, pageids as ids
from librescreen.util.cpp import jget, json_dump, jstr, substr

log = logging.getLogger(__name__)


def _equals(text):
    return lambda line: line == text


def _starts(prefix):
    return lambda line: line.startswith(prefix)


def _contains(*parts):
    return lambda line: any(part in line for part in parts)


def _on_page(*pages):
    return g.screen.page in pages


def _klipper_ready(line):
    from librescreen.printer import klipper
    g.klippy.idle_timeout_state = "Ready"
    log.info("Klipper restarted and is ready, sending the subscriptions")
    g.klippy.webhooks_state = "ready"
    g.klippy.webhooks_state_message = "Klipper state: Ready"
    time.sleep(5)
    klipper.sub_object_status()
    time.sleep(2)
    klipper.get_object_status()
    g.levelling.all_level_saving = True
    log.info("State after the restart: %s", g.klippy.webhooks_state)


def _klipper_disconnected(line):
    from librescreen.printer import klipper
    klipper.sub_object_status()


def _pid_parameters(line):
    log.info("// PID parameters: ")


def _shaper_result(attr):
    def handle(line):
        m = re.search(r"(\d+\.\d+)", line[len("// Recommended shaper_type_x = "):])      # a decimal number
        if m:
            setattr(g.levelling, attr, m.group(0))
        log.debug("Got the input shaping result")
        log.info("%s = %s", attr, getattr(g.levelling, attr))
    return handle


def _z_position(line):
    start = line.find(">") + 1
    end = line[start:].find("<") - 1
    g.levelling.str_manual_level_offset = substr(line, start, end)
    log.debug("%s", substr(line, start, end))


def _move_home_tips(line):
    from librescreen.pages import move
    move.move_home_tips()


def _filament_tips(line):
    from librescreen.pages import filament
    filament.filament_tips()


def _move_tips(line):
    from librescreen.pages import move
    move.move_tips()


def _mcu_shutdown(line):
    g.klippy.webhooks_state_message = "Can not update MCU 'mcu' config as it is shutdown"


def _out_of_memory(line):
    g.screen.jump_memory_warning = True


def _error(line):
    from librescreen.printer import job
    g.screen.error_message = line
    job.detect_error()


def _filament_sensor(line):
    # 4.4.2 CLL support mates and hall filament width sensors
    from librescreen.printer import job
    g.files.filament_message = line
    job.check_filament_width()


def _level_step(page_steps):
    """A calibration message sets a step flag, when the page that waits for it is open."""
    def handle(line):
        for pages, step in page_steps:
            if _on_page(*pages):
                setattr(g.levelling, step, True)
    return handle


def _bed_mesh_complete(line):
    if _on_page(ids.AUTO_MOVING):
        g.levelling.step_4 = True


def _load_finished(line):
    if _on_page(ids.AUTO_UNLOAD, ids.FILAMENT_POP_2, ids.FILAMENT_POP_3):
        g.levelling.step_2 = True
        log.debug("load / unload filament success, step_2=%d", 1)


def _filament_runout(line):
    g.klippy.filament_detected = False


# Events of the LibreQ1Pro Klipper macros: "// action:librescreen <event>"
EVENT_PREFIX = "// action:librescreen "
EVENTS = {
    "homed": _level_step([((ids.AUTO_MOVING,), "step_1")]),
    "nozzle_cleared": _level_step([((ids.AUTO_MOVING,), "step_2")]),
    "nozzle_cooled": _level_step([((ids.AUTO_MOVING,), "step_3")]),
    "bed_mesh_done": _bed_mesh_complete,
    "input_shaping_done": _level_step([((ids.SYNTONY_MOVE,), "step_1")]),
    "filament_heated": _level_step([((ids.FILAMENT_POP_2, ids.FILAMENT_POP_3, ids.AUTO_UNLOAD), "step_1")]),
    "filament_loaded": _load_finished,
    "filament_unloaded": _load_finished,
    "filament_runout": _filament_runout,
    # The print pauses: the printing pages show the pause from the print state
    "filament_tangle": None,
}


def _event(line):
    name = line[len(EVENT_PREFIX):].strip()
    if name not in EVENTS:
        log.warning("Unknown event: %s", name)
    elif EVENTS[name]:
        EVENTS[name](line)


# (does the line match, what to do); the first rule that matches wins, a rule without an action ignores the line
RULES = [
    (_equals("// Klipper state: Ready"), _klipper_ready),
    (_equals("// Klipper state: Disconnect"), _klipper_disconnected),
    (_starts("// PID parameters: "), _pid_parameters),
    (_equals("// action:cancel"), None),
    (_starts(EVENT_PREFIX), _event),
    (_starts("!! Must home axis first"), _move_home_tips),
    (_starts("!! Extrude below minimum temp"), _filament_tips),
    (_starts("// Recommended shaper_type_x = "), _shaper_result("shaper_freq_x")),
    (_starts("// Recommended shaper_type_y = "), _shaper_result("shaper_freq_y")),
    (_starts("// Z position:"), _z_position),
    (_starts("!! Move out of range:"), _move_tips),
    (_starts("!! Can not update MCU 'mcu' config as it is shutdown"), _mcu_shutdown),
    (_starts("// accelerometer values (x, y, z)"), None),
    (_starts("// Lost comm"), None),
    (_equals("Can not update"), None),
    (_contains("Result is z="), None),      # 4.4.3 CLL the z-offset is saved once the printer is ready again
    (_equals("!! Insufficient disk space, unable to read the file."), _out_of_memory),
    (_contains("!! Printer is not ready"), None),
    (_starts("!!"), _error),
    (_contains("// Filament dia (measured mm):", "// Filament NOT present"), _filament_sensor),
    (_starts("// metadata="), None),     # 4.1.7 CLL web print information subscription (deprecated)
    (_contains("echo: Detected unexpected interruption during the last print.", "echo: Yes: RESUME_INTERRUPTED",
               "echo: No: CLEAR_LAST_FILE"), None),
]


def parse_gcode_response(params):
    log.debug("%s", json_dump(params))
    if params is None:
        return
    line = jstr(jget(params, 0))

    # 4.4.2 CLL screen sleep feature
    if g.screen.page == ids.SCREEN_SLEEP:   # SCREEN_SLEEP has no refresh function, switching pages here can't conflict
        navigation.page_to(g.screen.previous_page)

    for matches, handle in RULES:
        if matches(line):
            if handle:
                handle(line)
            break
