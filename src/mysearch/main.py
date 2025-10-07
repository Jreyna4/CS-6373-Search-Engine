"""CSCI 6373 — Part 1 launcher (GUI by default; CLI with --cli)

Purpose
-------
Launch the Tkinter GUI by default so teammates can run the project from one
entrypoint. If you need the assignment's CLI loop for grading, pass --cli.

PyInstaller-friendly
--------------------
Uses absolute imports from the `mysearch` package and adds the package root to
`sys.path` when run as a script or frozen, so imports work reliably.

Usage
-----
# GUI (default)
python -m mysearch.main

# CLI (only when needed)
python -m mysearch.main --cli
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the package root is importable when run as a script or frozen
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_ROOT not in sys.path:
    sys.path.append(_PKG_ROOT)

# Absolute imports (work in module mode, script mode, and PyInstaller)
from mysearch.gui import MySearchGUI
from mysearch.parser import build_index, search_files


def run_gui() -> None:
    app = MySearchGUI()
    app.mainloop()


def run_cli() -> None:
    print("Beginning Search:")
    idx = build_index()
    while True:
        key = input("enter a search key=> ").strip()
        if key == "":
            print("Bye")
            break
        hits = search_files(idx, key)
        if hits:
            for m in hits:
                print(f"found a match:  ./Jan/{Path(m).name}")
        else:
            print("no match")


def main() -> None:
    parser = argparse.ArgumentParser(description="CSCI 6373 Part 1 launcher (GUI default)")
    parser.add_argument("--cli", action="store_true", help="Run the spec-compliant CLI instead of the GUI")
    args = parser.parse_args()
    if args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
