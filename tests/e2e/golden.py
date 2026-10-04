#!/usr/bin/env python3
"""
Golden traces of the Python port alone (the C++ reference is obsolete since the port follows firmware 4.4.24).
Every scenario of harness/scenarios.py runs in the librescreen-port-test container (tests/e2e/build_image.sh); the normalised trace (screen
instructions, Moonraker traffic, shell commands, touched files) is stored in golden/ or compared with it.
A refactoring must leave the traces unchanged; a change of behaviour shows up as a diff and is recorded on purpose.

    tests/e2e/golden.py record [-j 4] [scenario ...]    # (re)write golden/<scenario>.json
    tests/e2e/golden.py check  [-j 4] [scenario ...]    # compare; exit 1 on a difference
"""
import argparse
import concurrent.futures
import difflib
import json
import os
import sys
import re
import subprocess
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LIBRESCREEN_SRC") or os.path.dirname(os.path.dirname(HERE))   # src_py (or another checkout)
IMAGE = "librescreen-port-test:latest"
GOLDEN = os.path.join(HERE, "golden")
SECTIONS = ("pages", "screen", "ws", "http", "shell", "wpa", "files", "alive")


def all_scenarios():
    names = []
    with open(os.path.join(HERE, "harness", "scenarios.py")) as f:
        for line in f:
            m = re.match(r"def scenario_(\w+)\(", line)
            if m:
                names.append(m.group(1))
    return names


def run_one(scenario, out_dir, timeout):
    cmd = ["docker", "run", "--rm",
           "--tmpfs", "/home/mks/gcode_files/sda1",         # the USB drive: a mount point of its own
           "-v", "%s:/opt/src_py:ro" % ROOT,
           "-v", "%s:/opt/e2e:ro" % HERE,
           "-v", "%s:/out" % out_dir,
           IMAGE, "python3", "/opt/e2e/harness/harness.py", "--scenario", scenario, "--out", "/out"]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        output = "TIMEOUT"
    try:
        with open(os.path.join(out_dir, "py_%s.json" % scenario)) as f:
            return json.load(f), output
    except (OSError, ValueError):
        return None, output


def dedup(seq):
    out = []
    for item in seq:
        if not out or out[-1] != item:
            out.append(item)
    return out


def normalise(result):
    return {
        "screen": [{"page": v["page"], "attrs": v["attrs"]} for v in result["screen_visits"]],
        "pages": result["screen_pages"],
        "ws": dedup(result["ws_received"]),
        "http": dedup(result["http"]),
        "shell": dedup(result["shell"]),
        "wpa": dedup(result["wpa"]),
        "files": result["files"],
        "alive": result["exit_code_before_kill"] is None,
    }


def unknown_objects(result):
    return result.get("unknown_objects", [])


def fmt_lines(value):
    return json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True).split("\n")


def trace(scenario, out_dir, timeout):
    result, output = run_one(scenario, out_dir, timeout)
    if result is None:
        return None, output
    now = normalise(result)
    now["unknown_objects"] = unknown_objects(result)
    return now, output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("record", "check"))
    ap.add_argument("scenarios", nargs="*")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    scenarios = args.scenarios or all_scenarios()
    os.makedirs(GOLDEN, exist_ok=True)
    failed = 0
    with tempfile.TemporaryDirectory() as out_dir, concurrent.futures.ThreadPoolExecutor(args.jobs) as ex:
        futures = {ex.submit(trace, s, out_dir, args.timeout): s for s in scenarios}
        results = {}
        for fut in concurrent.futures.as_completed(futures):
            results[futures[fut]] = fut.result()
    for s in scenarios:
        now, output = results[s]
        path = os.path.join(GOLDEN, s + ".json")
        if now is None:
            print("FAIL  %-20s no trace\n%s" % (s, output[-500:]))
            failed += 1
        elif args.mode == "record":
            now = {k: v for k, v in now.items() if k != "unknown_objects"}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(now, f, indent=1, ensure_ascii=False, sort_keys=True)
                f.write("\n")
            print("wrote %s" % s)
        else:
            try:
                with open(path, encoding="utf-8") as f:
                    old = json.load(f)
            except OSError:
                print("FAIL  %-20s no golden trace" % s)
                failed += 1
                continue
            for entry in now["unknown_objects"]:
                print("BAD   %-20s the screen has no such object: %s" % (s, entry))
            failed += bool(now["unknown_objects"])
            bad = [k for k in SECTIONS if old[k] != now[k]]
            if bad:
                failed += 1
                print("FAIL  %-20s %s" % (s, ", ".join(bad)))
                for k in bad:
                    diff = difflib.unified_diff(fmt_lines(old[k]), fmt_lines(now[k]),
                                                "golden/" + k, "now/" + k, n=2, lineterm="")
                    print("\n".join("      " + l for l in list(diff)[:60]))
            else:
                print("OK    %s" % s)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
