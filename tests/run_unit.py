#!/usr/bin/env python3
"""Runs the unit tests, in the order of the files or in a random one (a test that depends on the one before it shows up):

    tests/run_unit.py                      # in docker (librescreen-port-test), the tests in the order they are found
    tests/run_unit.py --shuffle [SEED]     # in a random order (the seed is printed, the same seed gives the same order)
    tests/run_unit.py --shuffle --repeat 5 # five random orders

Nothing of the printer is touched: the tests run in the librescreen-port-test container with the source mounted read-only.
"""
import argparse
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run_in_docker(extra):
    cmd = ["docker", "run", "--rm", "-v", "%s:/opt/src_py:ro" % ROOT, "-w", "/opt/src_py", "-e", "PYTHONDONTWRITEBYTECODE=1", "librescreen-port-test:latest",
           "python3", "tests/run_unit.py", "--inside"] + extra
    return subprocess.call(cmd)


def inside(shuffle, seed):
    import unittest
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(HERE, "unit"))
    suite = unittest.defaultTestLoader.discover(os.path.join(HERE, "unit"))

    def flatten(item):
        for test in item:
            if isinstance(test, unittest.TestSuite):
                yield from flatten(test)
            else:
                yield test

    tests = list(flatten(suite))
    if shuffle:
        random.Random(seed).shuffle(tests)
        print("random order, seed %d" % seed)
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
    return 0 if result.wasSuccessful() else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shuffle", nargs="?", const=-1, type=int, metavar="SEED", help="a random order (the seed is chosen when it is not given)")
    ap.add_argument("--repeat", type=int, default=1, help="how many orders (with --shuffle)")
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.inside:
        return inside(args.shuffle is not None, args.shuffle if args.shuffle not in (None, -1) else random.randrange(1 << 30))
    status = 0
    for i in range(args.repeat):
        seed = args.shuffle if args.shuffle not in (None, -1) else random.randrange(1 << 30)
        extra = ["--shuffle", str(seed + i if args.shuffle not in (None, -1) else seed)] if args.shuffle is not None else []
        status |= run_in_docker(extra)
    return status


if __name__ == "__main__":
    sys.exit(main())
