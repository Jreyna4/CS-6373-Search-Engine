"""CSCI 6373 — Part 1 launcher (GUI by default; CLI with --cli)

Purpose
-------
Launch the Tkinter GUI by default so teammates can run the project from one
entrypoint. If you need the assignment's CLI loop for grading, pass --cli.

How it works
------------
- GUI (default): imports `MySearchGUI` and starts `mainloop()`.
- CLI (optional terminal testing): same spec loop as before.

Usage
-----
# GUI (default)
python -m mysearch.main

# CLI (only when needed)
python -m mysearch.main --cli
"""
import argparse
from pathlib import Path

try:
    from .gui import MySearchGUI
    from .parser import build_index, search_files
except ImportError:
    import os, sys, importlib
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _gui = importlib.import_module("mysearch.gui")
    MySearchGUI = _gui.MySearchGUI
    _parser = importlib.import_module("mysearch.parser")
    build_index = _parser.build_index
    search_files = _parser.search_files


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
