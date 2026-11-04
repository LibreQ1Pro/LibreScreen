#!/usr/bin/env python3
"""
Interactive printer for screen development - runs INSIDE the librescreen-port-test image (start it with
``tests/e2e/emulator.py``). Instead of the harness' recording screen it runs the HMI emulator of hmi-builder
(docs/EMULATOR.md) on /dev/ttyS1, next to the fake Moonraker of the E2E tests and the port itself:

    browser (touch screen)  <->  hmi_emulator.py  <-- /dev/ttyS1 -->  librescreen (main.py)  <->  fake Moonraker

The fake Moonraker takes commands over HTTP so that the printer can be played from a shell or the browser:

    POST /emu/status   {"extruder": {"temperature": 31.6}}        status update (notify_status_update)
    POST /emu/gcode    plain text                                  gcode response (notify_gcode_response)
    POST /emu/script   plain text                                  run a gcode script (changes heater targets)
    (a print job - printer.print.start, PAUSE / RESUME / CANCEL_PRINT - heats, runs for its estimated time / 20, completes)
    POST /emu/notify   {"method": "notify_klippy_shutdown"}       any notification ("params" optional)
    POST /emu/preset/<name>                                        a ready-made situation, see PRESETS
    GET  /emu/state                                                status objects, requests of the port

Heaters: a target set by the port (M104/M109/M140/M190/M141/M191, SET_HEATER_TEMPERATURE, TURN_OFF_HEATERS) is
approached by the temperature every second (and the ambient 25 degrees when the target is 0). M109 / M190 do not
block: Klipper's answer comes at once, the port follows the temperatures.
Wi-Fi: the fake nmcli shows three networks whose password is their own name (12345678, qwerty123, letmein99).
"""

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fixtures                     # noqa: E402
import harness                      # noqa: E402

PRESETS = {
    "idle": {"print_stats": {"state": "standby", "filename": "", "print_duration": 0.0},
             "display_status": {"progress": 0.0}, "pause_resume": {"is_paused": False},
             "idle_timeout": {"state": "Idle"}},
    "heating": {"extruder": {"temperature": 120.0, "target": 220.0}, "heater_bed": {"temperature": 45.0, "target": 60.0}},
    "printing": {"print_stats": {"state": "printing", "filename": "cube.gcode", "print_duration": 600.0,
                                 "filament_used": 1500.0},
                 "display_status": {"progress": 0.35}, "idle_timeout": {"state": "Printing"},
                 "extruder": {"temperature": 220.0, "target": 220.0}, "heater_bed": {"temperature": 60.0, "target": 60.0}},
    "paused": {"print_stats": {"state": "paused"}, "pause_resume": {"is_paused": True}},
    "complete": {"print_stats": {"state": "complete"}, "display_status": {"progress": 1.0},
                 "idle_timeout": {"state": "Ready"}},
    "cancelled": {"print_stats": {"state": "cancelled", "filename": ""}, "idle_timeout": {"state": "Ready"}},
    "runout": {"filament_switch_sensor fila": {"filament_detected": False}},
    "shutdown": {"webhooks": {"state": "shutdown", "state_message": "MCU shutdown (emulated)"}},
}


# heater -> (Klipper object, heating rate, cooling rate in degrees per second). Faster than the real ones so that
# the steps that wait for a temperature do not take minutes.
HEATERS = {
    "extruder": ("extruder", 6.0, 3.0),
    "heater_bed": ("heater_bed", 1.5, 0.3),
    "chamber": ("heater_generic chamber", 0.5, 0.1),
}
AMBIENT = 25.0
TICK = 1.0

# Macros of the LibreQ1Pro Klipper configuration (config/qidi-q1-pro/gcode_macro.cfg) that the port starts;
# they report the "// action:librescreen <event>" events with _LIBRESCREEN.
MACROS = {
    "M604": ["_LIBRESCREEN EVENT=filament_heated", "M83", "G1 E80 F400", "M400", "_LIBRESCREEN EVENT=filament_loaded"],
    "M603": ["_LIBRESCREEN EVENT=filament_heated", "G92 E0", "G0 E15 F400", "G4 P1000", "G92 E0", "G1 E-90 F800", "M400",
             "_LIBRESCREEN EVENT=filament_unloaded"],
}
FANS = {"0": "cooling_fan", "2": "auxiliary_cooling_fan", "3": "chamber_circulation_fan"}      # M106 P<n>
TARGET_CMD = {"M104": "extruder", "M109": "extruder", "M140": "heater_bed", "M190": "heater_bed",
              "M141": "chamber", "M191": "chamber"}
MOVE_SPEED = 1.0        # execution speed of moves: 1.0 = as long as the real printer takes
WAIT_LIMIT = 900.0


class GcodeError(Exception):
    """A command Klipper refuses: the message is answered as ``!! message`` and the rest of the script is dropped."""


MIN_EXTRUDE_TEMP = 170.0
HOME_POSITION = (125.0, 125.0, 10.0)        # where the axes stand after G28


PRINT_SPEEDUP = 20.0            # a print takes its estimated time divided by this
PRINT_TEMPS = {"extruder": 220.0, "heater_bed": 60.0}


class Moonraker(harness.Moonraker):
    """The fake Moonraker of the tests plus the /emu/ control interface, heaters that really heat and a gcode
    queue: scripts run one after the other like in Klipper (waits for temperatures, moves take their time, M118
    answers, idle_timeout is "Printing" meanwhile and "Ready" afterwards)."""

    def __init__(self, fixture):
        harness.Moonraker.__init__(self, fixture)
        self.scripts = queue.Queue()
        self.relative = False           # G91
        self.timelapse = False
        self.job = None                 # {"filename", "estimate", "elapsed", "phase": heating|printing|paused}

    def _handle_rpc(self, req):
        method = req.get("method")
        if method == "printer.gcode.script":
            self.scripts.put((req.get("params") or {}).get("script", ""))
        elif method == "printer.print.start":
            self.start_job((req.get("params") or {}).get("filename", ""))
        elif method == "printer.print.pause":
            self.scripts.put("PAUSE")
        elif method == "printer.print.resume":
            self.scripts.put("RESUME")
        elif method == "printer.print.cancel":
            self.scripts.put("CANCEL_PRINT")
        return super()._handle_rpc(req)

    # -- gcode ---------------------------------------------------------------
    def run_scripts(self):
        while True:
            script = self.scripts.get()
            printing = self.state.get("print_stats", {}).get("state") == "printing"
            if not printing:
                self.push_status({"idle_timeout": {"state": "Printing"}})
            for line in script.splitlines():
                try:
                    self.execute(line)
                except GcodeError as e:
                    self.push_gcode("!! " + str(e))
                    break               # Klipper drops the rest of the script (a G91 stays in force)
                except Exception:
                    import traceback
                    traceback.print_exc()
            if self.scripts.empty() and not printing:
                self.push_status({"idle_timeout": {"state": "Ready"}})

    def set_target(self, name, target):
        self.push_status({HEATERS[name][0]: {"target": float(target)}})

    # -- print job -------------------------------------------------------------------------------------------
    def start_job(self, filename):
        meta = self.metadata.get(filename) or {}
        estimate = float(meta.get("estimated_time") or 600) / PRINT_SPEEDUP
        self.job = {"filename": filename, "estimate": max(estimate, 20.0), "elapsed": 0.0, "phase": "heating",
                    "filament": float(meta.get("filament_total") or 1000)}
        self.push_status({"print_stats": {"state": "printing", "filename": filename, "print_duration": 0.0,
                                          "total_duration": 0.0, "filament_used": 0.0, "message": ""},
                          "display_status": {"progress": 0.0}, "pause_resume": {"is_paused": False},
                          "idle_timeout": {"state": "Printing"}})
        for name, target in PRINT_TEMPS.items():
            self.set_target(name, target)

    def end_job(self, state):
        self.job = None
        self.push_status({"print_stats": {"state": state}, "pause_resume": {"is_paused": False},
                          "idle_timeout": {"state": "Ready"}})
        for name in HEATERS:
            self.set_target(name, 0)

    def simulate_job(self):
        while True:
            time.sleep(1.0)
            job = self.job
            if job is None or job["phase"] == "paused":
                continue
            if job["phase"] == "heating":
                if (self.temperature("extruder") >= PRINT_TEMPS["extruder"] - 1
                        and self.temperature("heater_bed") >= PRINT_TEMPS["heater_bed"] - 1):
                    job["phase"] = "printing"
                continue
            job["elapsed"] += 1.0
            progress = min(job["elapsed"] / job["estimate"], 1.0)
            self.push_status({"print_stats": {"print_duration": job["elapsed"] * PRINT_SPEEDUP,
                                              "total_duration": job["elapsed"] * PRINT_SPEEDUP,
                                              "filament_used": round(job["filament"] * progress, 1)},
                              "display_status": {"progress": round(progress, 4)}})
            if progress >= 1.0:
                self.end_job("complete")

    # -- motion ----------------------------------------------------------------------------------------------
    def position(self):
        return list(self.state["toolhead"]["position"])

    def homed(self):
        return self.state["toolhead"].get("homed_axes", "")

    def set_position(self, pos):
        pos = [round(v, 3) for v in pos]
        self.push_status({"toolhead": {"position": pos}, "gcode_move": {"position": pos, "gcode_position": pos}})

    def set_homed(self, axes):
        self.push_status({"toolhead": {"homed_axes": "".join(a for a in "xyz" if a in axes)}})

    @staticmethod
    def format_position(pos):
        return "%.3f %.3f %.3f [%.3f]" % tuple(pos)

    def move(self, params):
        """G0 / G1: relative or absolute, checked like Klipper's cartesian kinematics."""
        cur = self.position()
        new = list(cur)
        for i, axis in enumerate("XYZ"):
            if axis in params:
                value = float(params[axis])
                new[i] = cur[i] + value if self.relative else value
        homed = self.homed()
        minimum = self.state["toolhead"]["axis_minimum"]
        maximum = self.state["toolhead"]["axis_maximum"]
        for i, axis in enumerate("xyz"):
            if abs(new[i] - cur[i]) < 1e-9 and axis in homed:
                continue
            if new[i] == cur[i]:
                continue
            if axis not in homed:
                raise GcodeError("Must home axis first: " + self.format_position(new))
            if not minimum[i] <= new[i] <= maximum[i]:
                raise GcodeError("Move out of range: " + self.format_position(new))
        speed = float(params.get("F", 1500)) / 60.0
        if "E" in params and float(params["E"]) != 0:
            if self.state.get("extruder", {}).get("temperature", 0) < MIN_EXTRUDE_TEMP:
                raise GcodeError("Extrude below minimum temp\nSee the 'min_extrude_temp' config option for details")
            distance = abs(float(params["E"]))
        else:
            distance = sum((new[i] - cur[i]) ** 2 for i in range(3)) ** 0.5
        time.sleep(min(distance / max(speed, 1.0) / MOVE_SPEED, 60) if distance else 0.05)
        new[3] = cur[3]
        self.set_position(new)

    def home(self, axes):
        pos = self.position()
        for axis in axes:
            pos["xyz".index(axis)] = HOME_POSITION["xyz".index(axis)]
        time.sleep(2)
        self.set_position(pos)
        self.set_homed(self.homed() + axes)

    def set_fan(self, name, speed):
        obj = "fan_generic " + name
        if obj in self.state:
            self.push_status({obj: {"speed": round(max(0.0, min(1.0, speed)), 3)}})

    def temperature(self, name):
        return self.state.get(HEATERS[name][0], {}).get("temperature", AMBIENT)

    def wait_temperature(self, name, low, high=None):
        deadline = time.time() + WAIT_LIMIT
        while time.time() < deadline:
            t = self.temperature(name)
            if t >= low and (high is None or t <= high):
                return
            time.sleep(0.2)

    def execute(self, line):
        line = line.split(";")[0].strip()
        words = line.split()
        if not words:
            return
        cmd = words[0].upper()
        params = {}
        for w in words[1:]:
            if "=" in w:
                params[w.split("=")[0].upper()] = w.split("=", 1)[1]
            else:
                params[w[0].upper()] = w[1:]
        if cmd in MACROS:
            for sub in MACROS[cmd]:
                self.execute(sub)
        elif cmd == "M118":
            self.push_gcode("echo: " + line[4:].strip())
        elif cmd == "_LIBRESCREEN":
            self.push_gcode("// action:librescreen " + params["EVENT"])
        elif cmd in ("M104", "M140", "M141") and "S" in params:
            self.set_target(TARGET_CMD[cmd], params["S"])
        elif cmd in ("M109", "M190", "M191") and "S" in params:
            target = float(params["S"])
            self.set_target(TARGET_CMD[cmd], target)
            if target != 0:
                # M109 of the QIDI configuration waits for target..target+1, the others for at least target
                self.wait_temperature(TARGET_CMD[cmd], target, target + 1 if cmd == "M109" else None)
        elif cmd == "SET_HEATER_TEMPERATURE":
            name = params.get("HEATER", "").replace("heater_generic ", "")
            if name in HEATERS:
                self.set_target(name, params.get("TARGET", 0))
        elif cmd == "TURN_OFF_HEATERS":
            for name in HEATERS:
                self.set_target(name, 0)
        elif cmd == "TEMPERATURE_WAIT":
            name = params.get("SENSOR", "").replace("heater_generic ", "")
            if name in HEATERS:
                self.wait_temperature(name, float(params.get("MINIMUM", 0)),
                                      float(params["MAXIMUM"]) if "MAXIMUM" in params else None)
        elif cmd == "PAUSE" and self.job:
            self.job["phase"] = "paused"
            self.push_status({"print_stats": {"state": "paused"}, "pause_resume": {"is_paused": True}})
        elif cmd == "RESUME" and self.job:
            self.job["phase"] = "printing"
            self.push_status({"print_stats": {"state": "printing"}, "pause_resume": {"is_paused": False}})
        elif cmd == "CANCEL_PRINT":
            self.end_job("cancelled")
        elif cmd in ("PRINT_END", "PRINT_END_POWEROFF"):     # heaters off; Klipper keeps "complete" until the file is reset
            for name in HEATERS:
                self.set_target(name, 0)
        elif cmd == "SDCARD_RESET_FILE":
            self.job = None
            self.push_status({"print_stats": {"state": "standby", "filename": "", "print_duration": 0.0},
                              "display_status": {"progress": 0.0}, "idle_timeout": {"state": "Ready"}})
        elif cmd == "M220" and "S" in params:
            self.push_status({"gcode_move": {"speed_factor": float(params["S"]) / 100.0}})
        elif cmd == "M221" and "S" in params:
            self.push_status({"gcode_move": {"extrude_factor": float(params["S"]) / 100.0}})
        elif cmd == "SET_GCODE_OFFSET" and "Z_ADJUST" in params:
            origin = list(self.state["gcode_move"]["homing_origin"])
            origin[2] = round(origin[2] + float(params["Z_ADJUST"]), 3)
            self.push_status({"gcode_move": {"homing_origin": origin}})
        elif cmd == "M106":
            fan = FANS.get(params.get("P", "0"))
            if fan:
                self.set_fan(fan, float(params["S"]) / 255.0 if "S" in params else 1.0)
        elif cmd == "M107":
            self.set_fan("cooling_fan", 0.0)
        elif cmd == "SET_FAN_SPEED":
            self.set_fan(params.get("FAN", ""), float(params.get("SPEED", 0)))
        elif cmd == "SET_PIN":                  # LED (caselight) and beeper (sound)
            if params.get("PIN") in ("caselight", "sound"):
                self.push_status({"output_pin " + params["PIN"]: {"value": float(params.get("VALUE", 0))}})
        elif cmd == "G4":
            time.sleep(min(float(params.get("P", 0)) / 1000.0, 30))
        elif cmd in ("G0", "G1"):
            self.move(params)
        elif cmd == "G90":
            self.relative = False
        elif cmd == "G91":
            self.relative = True
        elif cmd == "G28":
            self.home("".join(a for a in "xyz" if a.upper() in params) or "xyz")
        elif cmd == "SET_KINEMATIC_POSITION":       # pretends the axes are homed
            pos = self.position()
            for i, axis in enumerate("XYZ"):
                if axis in params:
                    pos[i] = float(params[axis])
            self.set_position(pos)
            self.set_homed(self.homed() + "".join(a.lower() for a in "XYZ" if a in params))
        elif cmd in ("M84", "M18", "SET_STEPPER_ENABLE"):
            if cmd != "SET_STEPPER_ENABLE" or params.get("ENABLE", "1") == "0":
                self.set_homed("")                  # motors off: the printer forgets where it is

    def simulate_heaters(self):
        """Moves every temperature towards its target (or the ambient one) and reports the changes."""
        while True:
            time.sleep(TICK)
            changes = {}
            for obj, up, down in HEATERS.values():
                cur = self.state.get(obj)
                if cur is None or "temperature" not in cur:
                    continue
                temp, target = cur["temperature"], cur.get("target") or 0.0
                goal = target if target > 0 else AMBIENT
                step = (up if goal > temp else down) * TICK
                new = round(goal if abs(goal - temp) <= step else temp + (step if goal > temp else -step), 1)
                if new != temp:
                    changes[obj] = {"temperature": new, "power": 1.0 if new < target else 0.0}
            if changes:
                self.push_status(changes)

    async def _http(self, request):
        from aiohttp import web
        path = request.path
        if path == "/machine/timelapse/settings":       # Moonraker's timelapse plugin (preview page switch)
            if request.method == "POST" and "enabled" in request.query:
                self.timelapse = request.query["enabled"].lower() == "true"
                with self.lock:
                    self.http.append("%s %s" % (request.method, request.path_qs))
            return web.json_response({"result": {"enabled": self.timelapse, "mode": "layermacro"}})
        if not path.startswith("/emu/"):
            return await super()._http(request)
        try:
            if path == "/emu/state":
                with self.lock:
                    return web.json_response({"state": self.state, "ws_received": self.received[-50:],
                                              "http": self.http[-50:]})
            body = await request.text()
            if path == "/emu/status":
                self.push_status(json.loads(body))
            elif path == "/emu/gcode":
                self.push_gcode(body)
            elif path == "/emu/script":         # a gcode script as the port would send it (heaters, see above)
                self.scripts.put(body)
            elif path == "/emu/notify":
                msg = json.loads(body)
                self.notify(msg["method"], msg.get("params"))
            elif path.startswith("/emu/preset/"):
                name = path[len("/emu/preset/"):]
                if name not in PRESETS:
                    return web.json_response({"error": "presets: " + ", ".join(sorted(PRESETS))}, status=404)
                self.push_status(json.loads(json.dumps(PRESETS[name])))
            else:
                return web.json_response({"error": "unknown /emu/ command"}, status=404)
        except (ValueError, KeyError) as e:
            return web.json_response({"error": str(e)}, status=400)
        return web.json_response({"ok": True})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="boot_main", help="fixture options (see fixtures.OPTIONS)")
    ap.add_argument("--project", default="/opt/display_firmware")
    ap.add_argument("--builder", default="/opt/hmi-builder")
    ap.add_argument("--http", default="0.0.0.0:8765", help="web UI of the emulator")
    args = ap.parse_args()

    fixture = fixtures.Fixture(args.scenario)
    fixture.install()
    if os.path.lexists("/dev/ttyS1"):
        os.unlink("/dev/ttyS1")
    os.makedirs("/tmp/eeprom", exist_ok=True)
    emu = subprocess.Popen(
        [sys.executable, os.path.join(args.builder, "tools", "hmi_emulator.py"), args.project,
         "--pty", "/dev/ttyS1", "--http", args.http, "--watch", "--state-dir", "/tmp/eeprom"])
    for _ in range(100):
        if os.path.lexists("/dev/ttyS1"):
            break
        time.sleep(0.1)
    else:
        sys.exit("the emulator did not create /dev/ttyS1")

    mr = Moonraker(fixture)
    mr.host = "0.0.0.0"
    mr.start()
    threading.Thread(target=mr.simulate_heaters, daemon=True).start()
    threading.Thread(target=mr.run_scripts, daemon=True).start()
    threading.Thread(target=mr.simulate_job, daemon=True).start()
    # NetworkManager: a stateful stand-in with three networks (see fakenm/nmcli)
    shutil.copy(os.path.join(HERE, "fakenm", "nmcli"), "/usr/local/bin/nmcli")
    if os.path.exists("/tmp/fake_nm.json"):
        os.unlink("/tmp/fake_nm.json")

    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1", LIBRESCREEN_SHELL_LOG="/tmp/librescreen_shell.log")
    sut = subprocess.Popen(["python3", "/opt/src_py/main.py", "localhost"], env=env, cwd="/")
    print("librescreen started; web UI of the screen on port %s, control on 7125 (/emu/...)" % args.http.rsplit(":", 1)[-1],
          flush=True)

    def commands():
        # shell commands of the port (systemctl, reboot, ...) go to stubs; show them
        seen = 0
        while True:
            time.sleep(1)
            try:
                with open("/tmp/librescreen_shell.log", "rb") as f:
                    data = f.read()
            except OSError:
                continue
            cmds = [c for c in data.split(b"\x1e") if c]
            for c in cmds[seen:]:
                print("shell: " + c.decode("utf-8", "replace"), flush=True)
            seen = len(cmds)
    threading.Thread(target=commands, daemon=True).start()

    try:
        while sut.poll() is None and emu.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    for p in (sut, emu):
        if p.poll() is None:
            p.terminate()
    print("librescreen exit code %r, emulator exit code %r" % (sut.poll(), emu.poll()), flush=True)


if __name__ == "__main__":
    main()
