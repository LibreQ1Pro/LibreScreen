#!/usr/bin/env python3
"""
Monkey test of the Python port: a virtual screen that touches everything in a random order with random pauses while the fake Moonraker changes the state of
the printer (harness/monkey.py). Every seed is one run in its own librescreen-port-test container; a seed that fails is repeated with
the same actions (the timing of the program is not under control, so a race may need more than one run).

    tests/e2e/monkey.py [--seeds 8] [--first 1] [--steps 150] [--hostile] [-j 4]      # seeds first .. first+seeds-1
    tests/e2e/monkey.py --seed 5 --steps 300 --keep                                     # one seed, keep the log and the actions in ./monkey_out/

Exit code 1 when a run found something.
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LIBRESCREEN_SRC") or os.path.dirname(os.path.dirname(HERE))
IMAGE = "librescreen-port-test:latest"


def run_seed(seed, steps, hostile, out_dir, timeout):
    os.makedirs(out_dir, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--tmpfs", "/home/mks/gcode_files/sda1", "-v", "%s:/opt/src_py:ro" % ROOT, "-v", "%s:/opt/e2e:ro" % HERE, "-v", "%s:/out" % out_dir,
           IMAGE, "python3", "/opt/e2e/harness/harness.py", "--scenario", "monkey", "--seed", str(seed), "--steps", str(steps), "--out", "/out"]
    if hostile:
        cmd.append("--hostile")
    try:
        output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout).stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        output = "TIMEOUT"
    try:
        with open(os.path.join(out_dir, "py_monkey_%d.json" % seed), encoding="utf-8") as f:
            return json.load(f), output
    except (OSError, ValueError):
        return None, output


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=8, help="how many seeds")
    ap.add_argument("--first", type=int, default=1, help="the first seed")
    ap.add_argument("--seed", type=int, help="one seed (instead of --seeds)")
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--hostile", action="store_true", help="also send what Moonraker never sends (wrong types)")
    ap.add_argument("-j", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--keep", action="store_true", help="keep the logs and the results in ./monkey_out/")
    args = ap.parse_args()
    seeds = [args.seed] if args.seed is not None else list(range(args.first, args.first + args.seeds))
    base = os.path.abspath("monkey_out") if args.keep else tempfile.mkdtemp(prefix="monkey_")
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(args.j) as pool:
        futures = {pool.submit(run_seed, s, args.steps, args.hostile, os.path.join(base, str(s)), args.timeout): s for s in seeds}
        for future in concurrent.futures.as_completed(futures):
            seed = futures[future]
            result, output = future.result()
            if result is None:
                failed += 1
                print("FAIL  seed %-4d the run produced no result:\n%s" % (seed, output[-800:]))
                continue
            errors = result["errors"] + result.get("unknown_objects", [])[:0]
            stats = result.get("extra", {}).get("monkey", {}).get("stats", {})
            if errors:
                failed += 1
                print("FAIL  seed %-4d %s" % (seed, ", ".join("%s %d" % kv for kv in sorted(stats.items()))))
                for error in errors:
                    print("      " + error.replace("\n", "\n      "))
            else:
                print("OK    seed %-4d %s" % (seed, ", ".join("%s %d" % kv for kv in sorted(stats.items()))))
    if failed:
        print("\n%d of %d runs found something%s" % (failed, len(seeds), "; the logs are in %s" % base if args.keep else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
