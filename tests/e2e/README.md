# E2E tests of the Python port

The port runs in a simulated printer inside docker, and everything it does to the outside world is
recorded and compared with the golden traces of `golden/`. They exist so that a refactoring can be
checked: a trace must not change unless the behaviour was changed on purpose.

## How it works

`build_image.sh` builds the image `librescreen-port-test` (Debian with Python, Pillow and aiohttp; native
architecture, one minute). It holds only the test support: a `/bin/sh` wrapper that logs every
`system()` / `popen()` command, no-op stubs for system tools (`systemctl`, `dpkg`, `curl`, ...), and an
`LD_PRELOAD` shim (`timescale.c`) that shortens sleeps of 1.5 s and more to a quarter.

`harness/harness.py` runs inside the container and starts the port with

* a **virtual TJC screen** on a pty linked to `/dev/ttyS1`: it records every instruction (`page n`,
  `obj.attr=value`, `vis ...`, `cp0.write("...")`), injects touch (`0x65`), value (`0x71`) and keyboard
  (`0x70`) events and implements the firmware download (`whmi-wri`) and file transfer (`twfile`) protocols;
* a **fake Moonraker** (aiohttp): websocket JSON-RPC plus the HTTP API, backed by a fixture file tree;
  the scenarios push status updates, gcode responses and notifications through it;
* deterministic **fixtures** (`harness/fixtures.py`): `settings.ini`, gcode files with thumbnails, a USB
  drive, update packages, a screen firmware file.

Each scenario of `harness/scenarios.py` drives the port like a user would. The trace has every page visit
with the distinct values of every widget attribute, every websocket message and HTTP request, every shell
command, the touched files, and whether the port was still alive. Repetitions caused by the refresh loops
are collapsed, so timing does not matter, but order and content do.

## Monkey test

The golden traces check a few flows in a fixed order. `monkey.py` checks what they cannot: a virtual screen that touches whatever it finds, in a random
order and with random pauses (bursts of taps, values and keyboard text, noise on the serial line, a screen that does not always carry out `page n`),
while the fake Moonraker changes the state of the printer all the time (the temperatures, the state of the print, Klipper shutting down and coming
back, files, notifications, the websocket dropping, junk messages). A run is correct when the service is alive, has printed no traceback, logged only
known errors, and, once the printer is calm again, the screen can be brought back to the main page. The choices come from a seed, so a failure is repeated
with the same actions; when it fails the report has the last actions and what every thread of the service is doing (`kill -USR1`) and what it believes
(`kill -USR2`).

```sh
tests/e2e/monkey.py --seeds 16 -j 8                    # seeds 1..16, 150 steps each
tests/e2e/monkey.py --seed 5 --steps 300 --keep        # one seed; the log and the actions stay in ./monkey_out/
tests/e2e/monkey.py --seeds 8 --first 100 --hostile    # also what Moonraker never sends (wrong types)
```

`--hostile` runs are fuzzing: they show where the parsing of Moonraker's answers would fail on a type that a real Moonraker does not send.

## Running

```sh
tests/e2e/build_image.sh           # once
tests/e2e/golden.py check -j 22    # all scenarios at once; compare with golden/ (under a minute)
tests/e2e/golden.py check wifi     # selected scenarios
tests/e2e/golden.py record -j 22   # accept a deliberate change of behaviour
```

`LIBRESCREEN_SRC=<checkout>` runs the port of another checkout (to record the traces of an older commit).

A full run takes under a minute: the harness waits for the port to go quiet (nothing new on the screen for half a
second) instead of fixed pauses, and the time-outs are a few seconds.

A scenario also fails (`BAD`) when the port addresses an object, or an attribute of it, that the current page does not have (`version_txt.txt=...` on a
page without `version_txt`): the real screen answers such an instruction with `0x1a`. A step whose events are meant for
another page than the virtual screen shows is wrapped in `h.other_page_events()`.

## Running the port against the screen emulator

The golden traces use a recording virtual screen. For developing the screen project there is also the HMI emulator of
hmi-builder (`docs/EMULATOR.md`): it runs `display_firmware` itself (`Program.s`, page events, pictures, fonts) and the
browser acts as the touch panel.

```sh
tests/e2e/emulator.py                    # open http://127.0.0.1:8765/ ; --scenario boot_oobe | file_list | boot_interrupted ...
curl -X POST localhost:7125/emu/preset/printing
```

One container (`librescreen-port-test`) holds the emulator on `/dev/ttyS1`, the fake Moonraker of the tests and the port, so
nothing of the port runs on the development host. `display_firmware` is mounted and the emulator runs with `--watch`:
edit a page or `Program.s`, save, and the emulator reloads while the port keeps running (the port does not resend a page it
already showed, so touch the screen or use the page selector). hmi-builder is found like `display_firmware/tools/build_hmi.py`
does (`HMI_BUILDER`, or `--builder`).

The printer is played through the fake Moonraker (`harness/devserver.py`), which takes commands on port 7125:

| request | effect |
|---|---|
| `POST /emu/preset/<name>` | `idle`, `heating`, `printing`, `paused`, `complete`, `cancelled`, `runout`, `shutdown` |
| `POST /emu/status` `{"extruder": {"temperature": 150}}` | `notify_status_update` with these objects |
| `POST /emu/script` (gcode text) | runs a script as Klipper would: heater targets change (see below) |
| `POST /emu/gcode` (text) | `notify_gcode_response` |
| `POST /emu/notify` `{"method": "notify_klippy_shutdown", "params": []}` | any notification |
| `GET /emu/state` | status objects and the last requests of the port |

**Gcode and heaters.** The scripts of the port run one after the other like in Klipper. Targets (`M104`/`M109`, `M140`/`M190`,
`M141`/`M191`, `SET_HEATER_TEMPERATURE`, `TURN_OFF_HEATERS`) are approached every second (extruder 6 °C/s up and 3 down, bed
1.5 / 0.3, chamber 0.5 / 0.1, ambient 25 °C) and reported like `notify_status_update`. `M109`, `M190`, `M191` and
`TEMPERATURE_WAIT` wait for the temperature, `G1` with `E` takes as long as the extrusion, `M603` / `M604` (unload / load
filament) run the macros of the LibreQ1Pro Klipper configuration with their events (`// action:librescreen filament_heated`,
`// action:librescreen filament_loaded`),
`G0`/`G1` move the toolhead (absolute or relative with `G90`/`G91`, as long as the distance takes) and answer like Klipper when
an axis is not homed (`!! Must home axis first: x y z [e]`, the rest of the script is dropped and a `G91` stays in force), when
the target is out of range (`!! Move out of range`) or when extruding below 170 °C (`!! Extrude below minimum temp`); `G28`
homes (X and Y to 125, Z to 10), `SET_KINEMATIC_POSITION` pretends the axes are homed, `M84` (motors off) forgets the homing,
so the move page shows its "park all?" question after a power-up or after motors off; `M106`/`M107`/`SET_FAN_SPEED` set the three fans and `SET_PIN` the LED and the beeper, a print job runs when the port starts one (`printer.print.start`: heating to 220 / 60 °C, progress for the estimated time divided by 20, `complete`, which stays until `SDCARD_RESET_FILE`; `PAUSE`, `RESUME`, `CANCEL_PRINT` work; `M220`, `M221` and `SET_GCODE_OFFSET` change speed, flow and z offset), Moonraker's timelapse plugin answers on `/machine/timelapse/settings` (the preview page switch), and `idle_timeout` is `Printing` while a script runs and `Ready` afterwards. Klipper's reply to the RPC comes at once.
A load takes about 40 s (heating 25 → 250 °C) + 12 s.

**Wi-Fi.** `harness/fakenm/nmcli` stands in for NetworkManager (state in `/tmp/fake_nm.json`). Three networks are in range and the
password of each is its own name: `12345678`, `qwerty123`, `letmein99`. A wrong password fails after two seconds like a real
one; saved networks, autoconnect, forgetting, disconnect and the radio switch work. The wired interface is connected
(192.168.1.50).

Differences from the real printer: the emulator does not draw `col_pic` and does not take over the timing of the display;
the other system tools are stubs; the sleeps are the real ones.

## Scenarios

| Scenario | Covers |
|---|---|
| boot_main | start-up sequence, subscriptions, main page refresh, cached file picture (ColPic), LED / beeper / emergency stop |
| boot_oobe | out-of-box guide pages, filament steps, `switch` fall-through 72 → 11 → 12 |
| oobe_calibrate | guide heater bed page, automatic calibration steps (`// action:librescreen` events) |
| screen_update | firmware download with `--flash-screen` (whmi-wri protocol), then the update-finished page of the screen |
| boot_interrupted | power loss recovery question |
| no_cache | start without a cached file |
| file_list | file list pages, folders, USB / local, 112×112 thumbnails via `twfile`, preview pictures, back navigation |
| print_flow | starting a print, filament pop-ups, printing pages, keyboard values, z-offset, pause / resume, stop, completion |
| print_events | print started from the web UI, filament runout (switch and hall sensor), filament page while paused, print error |
| temperatures | filament page keyboards / limits, heaters, fans page, distances, printing page value events |
| move_page | moves and distances, homing / out-of-range / cold extrusion pop-ups |
| levelling | mesh table, auto levelling sequence, input shaping, probe / bltouch z-offset results |
| bed_calibration | manual bed screw calibration loop |
| settings | system info, log export to USB, restarts, guide switch, factory reset |
| errors | Klipper shutdown / error / ready, gcode errors, Klipper state messages, levelling error |
| notifications | all Moonraker notifications, error responses, and an invalid message (ignored) |
| screen_sleep | screen sleep with the LED and wake-up |
| filament | filament load / unload, automatic and manual |

## Unit tests

`tests/run_unit.py` runs them in docker; `--shuffle [SEED] [--repeat N]` runs them in random orders: every test starts from a clean state of the service
(`tests/unit/support.py`), so a test that depends on the one before it fails there.
