#!/usr/bin/env python3
"""
The port against the HMI emulator of hmi-builder (docs/EMULATOR.md): no printer and no screen needed.

    tests/e2e/emulator.py [--scenario boot_oobe] [--builder PATH] [--port 8765] [--shell]

Starts the librescreen-port-test container (tests/e2e/build_image.sh) with the port, the fake Moonraker of the E2E
tests and the emulator running the project of display_firmware with --watch. Open http://127.0.0.1:8765/ : the
page is the touch screen. Edit display_firmware and save: the emulator reloads, the port keeps running (the pages
the port sent are not resent: touch the screen or use the page selector to see the change).

The printer is played over HTTP on port 7125 (see harness/devserver.py):

    curl -X POST localhost:7125/emu/preset/printing          # idle heating printing paused complete runout shutdown ...
    curl -X POST localhost:7125/emu/status -d '{"extruder": {"temperature": 150, "target": 220}}'
    curl -X POST localhost:7125/emu/gcode -d '// message'
    curl localhost:7125/emu/state

--scenario takes the file tree and options of an E2E scenario (boot_oobe: guide, file_list: USB drive,
boot_interrupted: power-loss question, ...).  --shell opens a shell in the same kind of container instead.
Port 7125 is bound to localhost only.  Timing is real (the tests shorten the sleeps).
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PROJECT = os.path.join(ROOT, "display_firmware")


def find_builder():
    sys.path.insert(0, os.path.join(PROJECT, "tools"))
    import build_hmi
    return build_hmi.find_builder()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scenario", default="boot_main")
    ap.add_argument("--builder", help="hmi-builder checkout (default: as tools/build_hmi.py finds it)")
    ap.add_argument("--port", type=int, default=8765, help="web UI of the emulator on localhost")
    ap.add_argument("--shell", action="store_true")
    args = ap.parse_args()
    builder = args.builder or find_builder()
    cmd = ["docker", "run", "--rm", "--init"] + (["-it"] if sys.stdin.isatty() else []) + [
           "--tmpfs", "/home/mks/gcode_files/sda1", "-p", "127.0.0.1:%d:8765" % args.port, "-p", "127.0.0.1:7125:7125",
           "-v", "%s:/opt/src_py:ro" % ROOT,
           "-v", "%s:/opt/e2e:ro" % HERE,
           "-v", "%s:/opt/display_firmware:ro" % PROJECT,
           "-v", "%s:/opt/hmi-builder:ro" % builder,
           "librescreen-port-test:latest"]
    if args.shell:
        cmd.append("bash")
    else:
        cmd += ["python3", "/opt/e2e/harness/devserver.py", "--scenario", args.scenario]
    print("web UI: http://127.0.0.1:%d/" % args.port, flush=True)
    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
