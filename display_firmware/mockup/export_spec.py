#!/usr/bin/env python3
"""Export the firmware's complete geometry and native labels in all 13 languages."""
import json
from pathlib import Path

import audit

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    data = audit.result(audit.dump("audit=spec", 180000), "spec")
    (HERE / "spec.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("spec.json: %d variants, %d widgets, 13 languages" % (len(data), sum(len(s["widgets"]) for s in data)))
