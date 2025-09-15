# MySearchEngine.com — Part 1 (HTML Parser) + Plugin-Ready GUI

**Course:** CSCI 6373 — IR & Web Search  
**Goal (Part 1):** Parse the provided `Jan.zip`, extract **alphabetic-only** (A–Z) words (lowercased), and let the user search which HTML files contain a term.  
This repo includes a working **GUI** for Part 1, a spec‑compliant **CLI**, and a **plugin loader** so Parts 2–4 can be added later without editing the GUI again.

---

## What’s included
- **GUI (Tkinter)** — Part 1 implemented + **dynamic tabs** for future parts via a simple plugin registry
  - Part 1: Open a zip (or use default `Jan.zip`), **Extract**, then **Search** for a key
  - Left: list of indexed files + summary; Right: search box + match list
- **Plugin loader** — `plugins.py` declares a list of future tabs; for each, the GUI attempts to import the module and call `build_tab(parent)`. If the module doesn’t exist yet, the tab shows a placeholder.
- **CLI** — matches the assignment’s interactive loop (alphabetic terms, lowercase, “found a match” / “no match” formatting)
- **Parser utilities** — robust `Jan.zip` auto-locator (walks up parent dirs), tokenization, and search helpers
- **Tests** — minimal smoke test (`tests/test_parser.py`)
- **Requirements** — `beautifulsoup4` (GUI works with built-in `html.parser`), `pytest` for tests (optional)

---

## Project layout

```
CS-6373-Search-Engine/
├─ README.md
├─ requirements.txt
├─ Jan.zip                      # <-- Put the provided archive here (recommended)
├─ src/
│  └─ mysearch/
│     ├─ __init__.py
│     ├─ parser.py              # build_index(), build_index_at(), search_files()
│     ├─ gui.py                 # Tkinter app (Part 1 + plugin loader)
│     ├─ main.py                # Launcher — GUI by default; CLI with --cli
│     └─ plugins.py             # registry of future tabs: PLUGINS=[(title, "mysearch.partN"), ...]
└─ tests/
   └─ test_parser.py            
```

> **Zip location:** The parser *auto-locates* `Jan.zip` by searching the current working directory and its parents **and** the module's directory and its parents. Keeping `Jan.zip` in the repo root (as shown) is recommended.

---

## Setup

Use either **venv** or **Conda**.

### Option A — venv (built-in)
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Install deps
pip install -r requirements.txt
```

### Option B — Conda
```bash
conda create -y -n cs6373 python=3.11
conda activate cs6373
pip install -r requirements.txt
```

> **Linux Tkinter note:** If `tkinter` is missing: `sudo apt-get install -y python3-tk` (Ubuntu/Debian) or your distro equivalent.

---

## Running

> Make sure `Jan.zip` is present (repo root recommended). You can also choose a different zip from the GUI via **Open…**.

### GUI (default)
Launch the app from the `src` folder:
```bash
# from repo root:
cd src
python -m mysearch.main
```
**In the app:**
1. Click **Open…** to choose a zip *or* click **Use Default (Jan.zip)**.
2. Click **Extract** (left side) to build the index.
3. Enter a word in **Search key** and click **Search** (right side).  
   Matches appear as `./Jan/<file>.html`.

### CLI (for grading/tests only)
```bash
cd src
python -m mysearch.main --cli
```
Example session:
```
Beginning Search:
enter a search key=> subject
found a match:  ./Jan/aol.html
found a match:  ./Jan/fab.html
found a match:  ./Jan/quickies.html
found a match:  ./Jan/y2k.html
enter a search key=> 
Bye
```

> You can also run files directly (e.g., `python src/mysearch/main.py`) — import shims make this work — but **module mode** (`python -m ...`) is recommended.

---

## How it works (Part 1)

- **Parsing** (`parser.py`):
  - Locates `Jan.zip` robustly (walks up parents from both CWD and the module).
  - Reads only `*.html` entries from the zip.
  - Extracts **visible text** with **BeautifulSoup** (if installed), stripping `script/style/noscript` tags; falls back to a simple regex strip otherwise.
  - Tokenizes with the regex `[A-Za-z]+` and converts tokens to **lowercase**.
  - Builds an in-memory index: `filename -> set(tokens)`.
- **Searching**:
  - Lowercases the user key and checks membership in each file’s token set.
  - The GUI & CLI both format matches as `./Jan/<file>.html` per the spec.

---

## Plugin system (Parts 2–4)

1. **Declare the tab** in `src/mysearch/plugins.py`:
   ```python
   PLUGINS = [
       ("Part 2 — Crawler", "mysearch.part2"),
       ("Part 3 — Indexer", "mysearch.part3"),
       ("Part 4 — Ranking", "mysearch.part4"),
   ]
   ```

2. **Create the module** (e.g., `src/mysearch/part2.py`) with a single function:
   ```python
   # src/mysearch/part2.py
   from tkinter import ttk
   import tkinter as tk

   def build_tab(parent: ttk.Frame) -> ttk.Frame:
       root = ttk.Frame(parent, padding=12)
       root.pack(fill=tk.BOTH, expand=True)
       ttk.Label(root, text="Part 2 goes here", font=("Segoe UI", 12, "bold")).pack(anchor="w")
       # add your controls here...
       return root
   ```

3. **Run the GUI**. The new tab appears automatically.  
   If a listed module is missing, the tab shows a friendly placeholder.

*(Optional)* If a plugin needs extra packages, add them to `requirements.txt` (e.g., `requests` for a web crawler).

---

## IntelliJ IDEA / PyCharm tips

Create a **Run/Debug Configuration**:
- **Module name:** `mysearch.main`
- **Working directory:** `<repo>/src`
- **Program arguments:** *(leave empty for GUI)*, `--cli` to run the text loop
- Also: mark `src/` as **Sources Root** for best import resolution.

---

## Tests

```bash
pytest -q
```
The test only checks imports and API; it doesn’t require `Jan.zip`.

---

## Contributing (team workflow)

- Branches: `part-1/<name>`, `part-2/<name>`, etc.
- Small, focused commits (e.g., `parser: add robust zip locator`).
- Open PRs into `main`, get a quick teammate review.

---

## Troubleshooting

- **`Could not locate Jan.zip`**  
  Ensure the file exists. The parser searches the current working dir and its parents *and* the module’s dir and its parents. Keeping it at repo root is simplest.
- **GUI doesn’t launch**  
  Use module mode from `src`: `python -m mysearch.main`. On Linux, install `python3-tk`.
- **Unresolved reference 'mysearch' in IDE**  
  Mark `src/` as **Sources Root** (Project Structure → Modules → Sources) so the IDE knows where your package lives.
- **Wrong Python/venv**  
  Verify the interpreter (`python --version`) and that your environment is activated.

---

## License

For course use in CSCI 6373. Team members may reuse and extend for Parts 2–5.
