#!/usr/bin/env python3
"""Build the .HMI project of the screen with hmi-builder.

    python3 tools/build_hmi.py [OUT.HMI] [--no-lint]

hmi-builder is looked for in $HMI_BUILDER, then in ../../hmi-builder (a checkout or a submodule next to src_py's
parent), then in ~/Projects/QSART_Linux_EN/hmi-builder. The steps: the project lint, `validate`, `pack`, `hmi_parse --check`
and OUT.HMI.sha256. The .tft still comes from the USART HMI editor (File -> Output production file).
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
LINTS = ["lint_program.py", "lint_frames.py", "lint_page_ids.py", "lint_faces.py"]


def find_builder():
    candidates = [
        os.environ.get("HMI_BUILDER"),
        os.path.join(PROJECT, "..", "..", "hmi-builder"),
        os.path.expanduser("~/Projects/QSART_Linux_EN/hmi-builder"),
    ]
    for path in candidates:
        if path and os.path.isfile(os.path.join(path, "tools", "hmi_project.py")):
            return os.path.realpath(path)
    sys.exit("hmi-builder not found: set HMI_BUILDER to its checkout")


def run(*cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = os.path.abspath(args[0] if args else os.path.join(PROJECT, "out", "display.HMI"))
    tools = os.path.join(find_builder(), "tools")
    config = os.path.join(PROJECT, "project.json")

    if "--no-lint" not in sys.argv:
        for lint in LINTS:
            run(sys.executable, os.path.join(HERE, lint))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        os.remove(out)     # pack refuses to overwrite
    project = os.path.join(tools, "hmi_project.py")
    run(sys.executable, project, "validate", PROJECT, "--config", config)
    run(sys.executable, project, "pack", PROJECT, out, "--config", config)
    run(sys.executable, os.path.join(tools, "hmi_parse.py"), out, "--check")

    with open(out, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with open(out + ".sha256", "w") as f:
        f.write(f"{digest}  {os.path.basename(out)}\n")
    print(f"{out}\n{digest}")


if __name__ == "__main__":
    main()
