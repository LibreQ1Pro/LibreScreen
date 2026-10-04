"""
Monkey test: the virtual screen touches whatever it finds, in a random order and with random pauses, while the fake Moonraker changes the state of the
printer all the time; the program must not fall over, must not print a traceback and must still answer afterwards.

The choices come from ``random.Random(seed)``: a seed that found a bug is repeated with the same actions (the timing of the program is not under control,
so a bug that depends on a race may need a few runs of the same seed).  Run it with tests/e2e/monkey.py.

What a run checks:
* the program is alive after every step (it is the screen backend: it must never exit),
* no "Traceback" in its log (an exception of a thread is printed there, a handled one is logged by ``log.exception``),
* the errors it logs are the known ones (``KNOWN_ERRORS``): a new kind of error line is reported,
* after the chaos the state of the printer is made normal again and the program has to bring the screen back to the main page (a stuck page is a bug).
"""
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "/opt/src_py/display_firmware"
sys.path.insert(0, os.environ.get("LIBRESCREEN_SRC_DIR", "/opt/src_py"))
from librescreen.screen import pageids as ids          # noqa: E402

NAVIGATION = (0x1e, 0x1f, 0x20, 0x21)           # the four buttons of the bar at the bottom of the pages
FILES = ("cube.gcode", "Benchy PLA.gcode", "part_abs.gcode", "models/inner.gcode", "big_petg.gcode", "z_last.gcode", "no such file.gcode",
         "модель_детали.gcode", "very_long_name_" * 8 + ".gcode", "")
WIFI_NAMES = ("Home", "Cafe", "кириллица", "x" * 40, "")

# error lines of the program that are no bugs (the fake Moonraker has no timelapse, a dropped websocket is on purpose, ...)
KNOWN_ERRORS = (
    r"websocket",
    r"Connection (refused|reset|closed)",
    r"Timelapse (state|switch): HTTP Error 404",                 # the fake Moonraker has no timelapse plugin, like the printer
    r"rpc_messages: .*(Expecting|Extra data|Unterminated|Invalid control|is not a JSON object)",       # the junk the test sends on purpose: logged, not fatal
)


def touch_table():
    """{page id: [widget ids]} of the clicks the pages can send: ``prints 0x65,1`` + the page (``dp`` or a number) + the widget."""
    with open(os.path.join(PROJECT, "project.json"), encoding="utf-8") as f:
        pages = json.load(f)["pages"]
    table = {}
    for number, entry in enumerate(pages):
        with open(os.path.join(PROJECT, entry["content"]["path"]), encoding="utf-8") as f:
            page = json.load(f)
        for obj in page["objects"]:
            for event in obj["events"].values():
                for i, line in enumerate(event[:-2]):
                    if line.strip() != "prints 0x65,1":
                        continue
                    where, widget = event[i + 1].strip(), event[i + 2].strip()
                    target = number if where == "prints dp,1" else _number(where)
                    value = _number(widget)
                    if target is not None and value is not None:
                        table.setdefault(target, set()).add(value)
    return {page: sorted(widgets) for page, widgets in table.items()}


def _number(line):
    m = re.fullmatch(r"prints (0x[0-9a-fA-F]+|\d+),1", line)
    return int(m.group(1), 0) if m else None


def value_events():
    """(page, widget) pairs the host listens to for numbers (0x71): the keyboards of the temperatures, fans, speed and flow."""
    from librescreen.screen import events
    return sorted(events.SETTED)


class Monkey(object):
    def __init__(self, h, seed, steps, hostile):
        self.h, self.seed, self.steps, self.hostile = h, seed, steps, hostile
        self.rng = random.Random(seed)
        self.touches = touch_table()
        self.values = value_events()
        self.actions = []
        self.log_checked = 0
        self.stats = {}
        self.broken = False

    # -- the random choices ------------------------------------------------------------------------------------------
    def pause(self):
        r = self.rng.random()
        if r < 0.2:
            return 0.0
        if r < 0.6:
            return self.rng.uniform(0.02, 0.1)
        if r < 0.9:
            return self.rng.uniform(0.1, 0.5)
        return self.rng.uniform(1.0, 2.0)

    def note(self, kind, text=""):
        self.actions.append("%s %s" % (kind, text) if text else kind)
        self.stats[kind] = self.stats.get(kind, 0) + 1

    def step(self):
        actions = (
            (45, self.tap), (8, self.burst), (6, self.value), (5, self.keyboard), (14, self.status), (3, self.gcode), (3, self.notification),
            (2, self.wifi), (2, self.garbage), (2, self.hiccup), (10, self.wait))
        total = sum(w for w, _ in actions)
        r = self.rng.uniform(0, total)
        for weight, action in actions:
            r -= weight
            if r <= 0:
                return action()
        return self.wait()

    # -- the screen ----------------------------------------------------------------------------------------------------
    def a_click(self):
        """A page and a widget: usually what the screen shows and what it can send, sometimes a stray or an unknown one."""
        page = self.h.screen.page
        if page is None or self.rng.random() < 0.25:
            page = self.rng.choice(sorted(self.touches))
        r = self.rng.random()
        if r < 0.15:
            widget = self.rng.choice(NAVIGATION)
        elif r < 0.9 and self.touches.get(page):
            widget = self.rng.choice(self.touches[page])
        else:
            widget = self.rng.randrange(0, 48)
        return page, widget

    def tap(self):
        page, widget = self.a_click()
        self.note("tap", "%d/0x%02x" % (page, widget))
        self.h.screen.touch(page, widget)

    def burst(self):
        page, widget = self.a_click()
        count = self.rng.randrange(2, 7)
        self.note("burst", "%d/0x%02x x%d" % (page, widget, count))
        for _ in range(count):
            self.h.screen.touch(page, widget)
            time.sleep(self.rng.uniform(0, 0.03))

    def value(self):
        page, widget = self.rng.choice(self.values)
        number = self.rng.choice((0, 1, 5, 30, 60, 100, 150, 220, 250, 300, 350, 999, 4000, 65535, self.rng.randrange(0, 400)))
        self.note("value", "%d/%d=%d" % (page, widget, number))
        self.h.screen.set_number(page, widget, number)

    def keyboard(self):
        mode = self.rng.randrange(0, 7)
        text = self.rng.choice(("", "12345678", "пароль-кириллица", "a" * 200, "quote\"s and 'apostrophes'", "tab\tand\nnewline", "\u0000\u0001", "😀" * 5))
        raw = text.encode("utf-8")
        if self.rng.random() < 0.1:
            raw = bytes(self.rng.randrange(256) for _ in range(self.rng.randrange(1, 40))).replace(b"\xff\xff\xff", b"")
        self.note("keyboard", "mode %d %r" % (mode, raw[:20]))
        self.h.screen.send(bytes([0x70, mode, self.rng.randrange(0, 6)]) + raw + b"\xff\xff\xff")

    def garbage(self):
        """Noise on the serial line: random bytes, an unknown event, a cut frame."""
        kind = self.rng.choice(("noise", "unknown", "cut"))
        self.note("garbage", kind)
        if kind == "noise":
            self.h.screen.send(bytes(self.rng.randrange(256) for _ in range(self.rng.randrange(1, 64))).replace(b"\xff\xff\xff", b"\xfe\xff\xff") + b"\xff\xff\xff")
        elif kind == "unknown":
            self.h.screen.send(bytes([self.rng.choice((0x00, 0x03, 0x1a, 0x33, 0x66, 0x7f, 0x86, 0xfd)), self.rng.randrange(256), self.rng.randrange(256)]) + b"\xff\xff\xff")
        else:
            self.h.screen.send(bytes([0x65, self.rng.randrange(0, 90)]))
            time.sleep(self.rng.uniform(0.01, 0.2))
            self.h.screen.send(bytes([self.rng.randrange(0, 40), 1]) + b"\xff\xff\xff")

    # -- Moonraker ---------------------------------------------------------------------------------------------------
    def status(self):
        rng = self.rng
        choices = [
            lambda: {"extruder": {"temperature": round(rng.uniform(20, 300), 1), "target": rng.choice((0.0, 170.0, 220.0, 250.0, 300.0))}},
            lambda: {"heater_bed": {"temperature": round(rng.uniform(20, 120), 1), "target": rng.choice((0.0, 50.0, 60.0, 100.0))}},
            lambda: {"heater_generic chamber": {"temperature": round(rng.uniform(20, 60), 1), "target": rng.choice((0.0, 40.0, 60.0))}},
            lambda: {"print_stats": {"state": rng.choice(("standby", "printing", "paused", "complete", "cancelled", "error")),
                                     "filename": rng.choice(FILES), "print_duration": round(rng.uniform(0, 20000), 1),
                                     "total_duration": round(rng.uniform(0, 20000), 1), "filament_used": round(rng.uniform(0, 9000), 1)}},
            lambda: {"print_stats": {"info": {"current_layer": rng.randrange(0, 300), "total_layer": rng.choice((None, 0, 250))}}},
            lambda: {"display_status": {"progress": round(rng.random(), 3), "message": rng.choice((None, "", "hello"))}},
            lambda: {"virtual_sdcard": {"progress": round(rng.random(), 3), "is_active": rng.random() < 0.5}},
            lambda: {"idle_timeout": {"state": rng.choice(("Idle", "Ready", "Printing"))}},
            lambda: {"pause_resume": {"is_paused": rng.random() < 0.5}},
            lambda: {"webhooks": rng.choice(({"state": "ready", "state_message": "Printer is ready"},
                                             {"state": "startup", "state_message": "Printer is not ready"},
                                             {"state": "shutdown", "state_message": "MCU 'mcu' shutdown: Timer too close\nOnce the underlying issue is corrected"},
                                             {"state": "error", "state_message": "Unable to open config file\n" * 20}))},
            lambda: {"gcode_move": {"speed_factor": round(rng.uniform(0.1, 3.0), 2), "extrude_factor": round(rng.uniform(0.5, 2.0), 2),
                                    "homing_origin": [0.0, 0.0, round(rng.uniform(-3, 3), 3), 0.0]}},
            lambda: {"toolhead": {"position": [round(rng.uniform(-10, 270), 2), round(rng.uniform(-10, 270), 2), round(rng.uniform(-5, 260), 2), 0.0],
                                  "homed_axes": rng.choice(("", "x", "xy", "xyz", "z"))}},
            lambda: {"fan": {"speed": round(rng.random(), 2)}},
            lambda: {"fan_generic cooling_fan": {"speed": round(rng.random(), 2)}},
            lambda: {"fan_generic auxiliary_cooling_fan": {"speed": round(rng.random(), 2)}},
            lambda: {"fan_generic chamber_circulation_fan": {"speed": round(rng.random(), 2)}},
            lambda: {"output_pin caselight": {"value": float(rng.randrange(2))}},
            lambda: {"gcode_macro _SOUND": {"enabled": rng.randrange(2)}},
            lambda: {"filament_switch_sensor fila": {"filament_detected": rng.random() < 0.5}},
            lambda: {"probe": {"z_offset": round(rng.uniform(-3, 3), 3)}},
        ]
        if self.hostile:         # what Moonraker never sends: wrong types, missing fields
            choices += [
                lambda: {"extruder": {"temperature": rng.choice((None, "hot", [], -1e9, 1e12))}},
                lambda: {"print_stats": {"state": rng.choice((None, 5, "no-such-state", ""))}},
                lambda: {"toolhead": {"position": rng.choice((None, [], [1], "x"))}},
                lambda: {"webhooks": {"state": None, "state_message": None}},
            ]
        status = rng.choice(choices)()
        self.note("status", json.dumps(status, ensure_ascii=False)[:90])
        self.h.mr.push_status(status)

    def gcode(self):
        text = self.rng.choice(("ok", "// Probe at 100,100 is z=1.2", "!! Must home axis first: 125.000 125.000 10.000 [0.000]",
                                "!! Move out of range: 300.000 0.000 5.000 [0.000]", "Error: something\nwith two lines", "// " + "x" * 600, "", "!! \u0000"))
        self.note("gcode", repr(text[:40]))
        self.h.mr.push_gcode(text)

    def notification(self):
        method = self.rng.choice(("notify_klippy_ready", "notify_klippy_shutdown", "notify_klippy_disconnected", "notify_filelist_changed",
                                  "notify_history_changed", "notify_proc_stat_update", "notify_unknown_thing"))
        params = None
        if method == "notify_history_changed":
            params = [{"action": self.rng.choice(("added", "finished")), "job": {"filename": self.rng.choice(FILES), "status": "completed"}}]
        elif method == "notify_filelist_changed":
            params = [{"action": "create_file", "item": {"path": self.rng.choice(FILES), "root": "gcodes"}}]
        self.note("notify", method)
        self.h.mr.notify(method, params)

    def wifi(self):
        wpa = getattr(self.h, "wpa", None)
        if wpa is None:
            return self.wait()
        event = self.rng.choice(("CTRL-EVENT-CONNECTED ", "CTRL-EVENT-DISCONNECTED ", "CTRL-EVENT-SCAN-RESULTS ", "CTRL-EVENT-SSID-TEMP-DISABLED ", "garbage"))
        self.note("wifi", event.strip())
        wpa.event(event)

    def hiccup(self):
        kind = self.rng.choice(("drop", "mute", "junk"))
        self.note("moonraker", kind)
        if kind == "drop":
            self.h.mr.drop_connection()
        elif kind == "mute":
            self.h.mr.responses_enabled = False
            time.sleep(self.rng.uniform(0.5, 1.5))
            self.h.mr.responses_enabled = True
        else:
            self.h.mr.push_raw(self.rng.choice(("not json", "{", "[]", '{"jsonrpc":"2.0","method":"notify_status_update","params":[null]}', '{"id":1}', "")))

    def wait(self):
        self.note("wait")

    # -- the checks ----------------------------------------------------------------------------------------------------
    def check_alive(self):
        rc = self.h.proc.poll()
        if rc is not None:
            self.fail("the program exited (code %s)" % rc)
            return False
        return True

    def check_log(self):
        """Tracebacks and unknown kinds of error lines in what the program printed since the last look."""
        path = self.h.sut_log.name
        with open(path, "rb") as f:
            f.seek(self.log_checked)
            text = f.read().decode("utf-8", "replace")
            self.log_checked = f.tell()
        for number, line in enumerate(text.splitlines()):
            if line.startswith("Traceback"):
                excerpt = "\n".join(text.splitlines()[number:number + 14])
                self.fail("traceback in the log:\n" + excerpt)
            elif re.match(r"^E ", line) and not any(re.search(known, line) for known in KNOWN_ERRORS):
                self.fail("error in the log: " + line[:200])

    def threads(self):
        """What every thread of the program is doing (faulthandler, SIGUSR1): where a stuck program waits."""
        import signal
        mark = os.path.getsize(self.h.sut_log.name)
        try:
            os.kill(self.h.proc.pid, signal.SIGUSR2)
            time.sleep(0.5)
            os.kill(self.h.proc.pid, signal.SIGUSR1)
        except OSError:
            return "(the program cannot be asked what it is doing)"
        time.sleep(1.0)
        with open(self.h.sut_log.name, "rb") as f:
            f.seek(mark)
            dump = f.read().decode("utf-8", "replace")
        lines = [line for line in dump.splitlines() if line.startswith(("STATE", "Thread", "Current thread", "  File"))]
        return "the threads of the program:\n" + "\n".join(lines[:60])

    def fail(self, message):
        recent = "\n    ".join(self.actions[-12:])
        self.h.errors.append("seed %d, step %d: %s\n  the last actions:\n    %s" % (self.seed, len(self.actions), message, recent))

    # -- the end: everything normal again, the screen has to come back --------------------------------------------------
    def calm_down(self):
        h = self.h
        h.mr.responses_enabled = True
        h.mr.push_status({"webhooks": {"state": "ready", "state_message": "Printer is ready"},
                          "print_stats": {"state": "standby", "filename": ""}, "idle_timeout": {"state": "Ready"},
                          "pause_resume": {"is_paused": False}, "extruder": {"target": 0.0}, "heater_bed": {"target": 0.0}})
        h.mr.drain(timeout=90)          # the fake Moonraker sends one message in 0.3 s: the ones of the chaos are still on their way
        h.settle(3.0)

    def back_home(self):
        """The main page has to be reachable by what a user does: the buttons of the bar, then every button of the page, page after page (the setup guide
        is a row of pages that has to be gone through)."""
        h = self.h
        for hop in range(30):
            if h.screen.page == ids.MAIN:
                return True
            page = h.screen.page
            for widget in (0x1e,) + tuple(self.touches.get(page, ())):
                h.screen.touch(page if page is not None else ids.MAIN, widget)
                h.settle(1.0)
                if h.screen.page == ids.MAIN:
                    return True
                if h.screen.page != page:
                    break
        return h.screen.page == ids.MAIN

    def run(self):
        h = self.h
        h.mr.gap = 0.05                 # many messages are sent here: the pause of 0.3 s between two of them would keep the state of the program far behind
        h.wait_page(ids.MAIN, 180)
        h.settle(3.0)
        h.screen.page_loss = 0.15       # a screen that does not always do what it is told: the service has to notice (sendme) and switch again
        self.check_log()
        for number in range(self.steps):
            self.step()
            if not self.check_alive():
                break
            if number % 10 == 9:
                self.check_log()
            time.sleep(self.pause())
        h.settle(2.0)
        h.screen.page_loss = 0.0
        if self.check_alive():
            self.check_log()
            self.calm_down()
            if not self.back_home():
                self.fail("the screen is stuck on the page %s, the main page cannot be reached\n%s" % (h.screen.page, self.threads()))
            self.check_log()
        h.extra["monkey"] = {"seed": self.seed, "steps": len(self.actions), "stats": self.stats, "actions": self.actions,
                             "lost_pages": len(h.screen.lost_pages)}


def scenario_monkey(h):
    Monkey(h, h.options["seed"], h.options["steps"], h.options["hostile"]).run()
