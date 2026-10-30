#!/usr/bin/env python3
"""Launcher: ``python3 main.py [moonraker_host]`` (same as the C++ ``xindi`` binary)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xindi.main import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
