
"""CSCI 6373 — Part 1 Tkinter GUI (sketch-aligned + plugin loader + vocabulary view)

Purpose
-------
Implements your sketched layout for Part 1 and auto-loads future parts (Part 2–4)
from a simple registry in `plugins.py`. The Part 1 panel now shows:
- Indexed files (left/top)
- Vocabulary (unique extracted words, left/bottom)
- Key Search (right)

How it works
------------
- Part 1:
  - If a zip is chosen with **Open**, we index that exact file using
    `build_index_at(path)`; otherwise **Extract** falls back to `build_index()`
    which auto-locates `Jan.zip`.
  - After extraction, we populate BOTH lists: files and vocabulary.
- Plugins:
  - `plugins.py` defines: PLUGINS = [(tab_title, "mysearch.partN"), ...]
  - For each entry, we try to import the module and call `build_tab(parent)`.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Optional plugin registry
try:
    from .plugins import PLUGINS
except Exception:
    PLUGINS = []

# Imports that work in both module and direct-script modes
try:  # package/module run: python -m mysearch.gui
    from .parser import build_index, build_index_at, search_files
except ImportError:
    # direct script run: python path/to/src/mysearch/gui.py
    import os, sys, importlib
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # add <repo>/src
    _parser = importlib.import_module("mysearch.parser")
    build_index = _parser.build_index
    build_index_at = _parser.build_index_at
    search_files = _parser.search_files


class MySearchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MySearchEngine.com — CSCI 6373")
        self.geometry("1000x680")

        self.selected_zip: Path | None = None
        self.index = None  # Dict[str, Set[str]]

        # ---- Header ----
        header = ttk.Frame(self, padding=(12, 8))
        header.pack(fill=tk.X)
        ttk.Label(header, text="CSCI 6373", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text="   Group #:", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(16, 4))
        self.group_var = tk.StringVar(value="TBD")
        ttk.Entry(header, textvariable=self.group_var, width=10).pack(side=tk.LEFT)

        # ---- Notebook ----
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Part 1 tab
        self.tab_p1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_p1, text="Part 1 — HTML Parser")
        self._build_part1(self.tab_p1)

        # "Currently selected" indicator
        indicator = ttk.Frame(self, padding=(12, 0))
        indicator.pack(fill=tk.X)
        self.current_tab_var = tk.StringVar(value="Currently selected: Part 1 — HTML Parser")
        ttk.Label(indicator, textvariable=self.current_tab_var).pack(side=tk.LEFT)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Dynamic plugin tabs (Part 2–4, etc.) from PLUGINS
        self._load_plugins()

    # ---------- Plugin Loader ----------
    def _load_plugins(self):
        import importlib
        for title, modname in PLUGINS:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=title)
            try:
                mod = importlib.import_module(modname)
                if hasattr(mod, "build_tab"):
                    mod.build_tab(tab)  # plugin owns its UI
                else:
                    ttk.Label(tab, text=f"{modname} missing build_tab(parent)", padding=24).pack()
            except Exception as e:
                ttk.Label(tab, text=f"{modname} not available: {e}", padding=24).pack()

    # ---------- Part 1 ----------
    def _build_part1(self, parent: ttk.Frame):
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        # Zip selection row
        zip_row = ttk.Frame(outer)
        zip_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(zip_row, text="Zip selection:").pack(side=tk.LEFT)
        ttk.Button(zip_row, text="Open…", command=self._on_open_zip).pack(side=tk.LEFT, padx=8)
        self.zip_name_var = tk.StringVar(value="File name: No file selected")
        ttk.Label(zip_row, textvariable=self.zip_name_var).pack(side=tk.LEFT, padx=8)
        ttk.Button(zip_row, text="Use Default (Jan.zip)", command=self._use_default_zip).pack(side=tk.RIGHT)

        ttk.Separator(outer, orient="horizontal").pack(fill=tk.X, pady=6)

        # Two-column area
        two_col = ttk.Frame(outer)
        two_col.pack(fill=tk.BOTH, expand=True)

        # Left column (Word Extraction): two stacked frames
        left = ttk.Frame(two_col, padding=(0, 0, 12, 0))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(left, text="Word Extraction", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Button(left, text="Extract", command=self._on_extract).pack(anchor="w", pady=(6, 6))

        # Indexed files list
        lf = ttk.LabelFrame(left, text="Indexed files")
        lf.pack(fill=tk.BOTH, expand=True)
        self.files_list = tk.Listbox(lf, height=12)
        yscroll1 = ttk.Scrollbar(lf, orient="vertical", command=self.files_list.yview)
        self.files_list.configure(yscrollcommand=yscroll1.set)
        self.files_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll1.pack(side=tk.RIGHT, fill=tk.Y)

        # Vocabulary list (unique words)
        wf = ttk.LabelFrame(left, text="Vocabulary (unique words)")
        wf.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.words_list = tk.Listbox(wf, height=12)
        yscrollw = ttk.Scrollbar(wf, orient="vertical", command=self.words_list.yview)
        self.words_list.configure(yscrollcommand=yscrollw.set)
        self.words_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscrollw.pack(side=tk.RIGHT, fill=tk.Y)

        self.summary_var = tk.StringVar(value="No index yet.")
        ttk.Label(left, textvariable=self.summary_var).pack(anchor="w", pady=(6, 0))

        # Vertical separator
        ttk.Separator(two_col, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=4)

        # Right: Key Search
        right = ttk.Frame(two_col, padding=(12, 0, 0, 0))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Key Search", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        search_row = ttk.Frame(right)
        search_row.pack(fill=tk.X, pady=(6, 6))
        ttk.Label(search_row, text="Search key:").pack(side=tk.LEFT)
        self.query_var = tk.StringVar()
        ent = ttk.Entry(search_row, textvariable=self.query_var, width=28)
        ent.pack(side=tk.LEFT, padx=8)
        ent.bind("<Return>", lambda e: self._on_search())
        ttk.Button(search_row, text="Search", command=self._on_search).pack(side=tk.LEFT)

        # Matches list
        rf = ttk.LabelFrame(right, text="Matches")
        rf.pack(fill=tk.BOTH, expand=True)
        self.results_list = tk.Listbox(rf, height=25)
        yscroll2 = ttk.Scrollbar(rf, orient="vertical", command=self.results_list.yview)
        self.results_list.configure(yscrollcommand=yscroll2.set)
        self.results_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll2.pack(side=tk.RIGHT, fill=tk.Y)

    # ---------- Callbacks ----------
    def _on_tab_changed(self, event=None):
        tab_text = self.notebook.tab(self.notebook.select(), "text")
        self.current_tab_var.set(f"Currently selected: {tab_text if tab_text else 'Unknown'}")

    def _on_open_zip(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Jan.zip",
            filetypes=[("Zip files", "*.zip")],
        )
        if not path:
            return
        self.selected_zip = Path(path)
        self.zip_name_var.set(f"File name: {self.selected_zip.name}")
        self.index = None
        self.files_list.delete(0, tk.END)
        self.words_list.delete(0, tk.END)
        self.results_list.delete(0, tk.END)
        self.summary_var.set("Ready to extract from selected zip.")

    def _use_default_zip(self):
        self.selected_zip = None
        self.zip_name_var.set("File name: No file selected (using default Jan.zip)")
        self.index = None
        self.files_list.delete(0, tk.END)
        self.words_list.delete(0, tk.END)
        self.results_list.delete(0, tk.END)
        self.summary_var.set("Ready to extract from default Jan.zip.")

    def _on_extract(self):
        try:
            if self.selected_zip is not None:
                self.index = build_index_at(self.selected_zip)
            else:
                self.index = build_index()
        except FileNotFoundError as e:
            messagebox.showerror("Zip not found", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build index: {e}")
            return

        # Populate files list & vocabulary
        self.files_list.delete(0, tk.END)
        self.words_list.delete(0, tk.END)
        vocab = set()
        for fname, terms in sorted(self.index.items()):
            self.files_list.insert(tk.END, f"./Jan/{Path(fname).name}")
            vocab |= terms

        for w in sorted(vocab):
            self.words_list.insert(tk.END, w)

        self.summary_var.set(f"Indexed {len(self.index)} files • Vocabulary size {len(vocab)}.")

    def _on_search(self):
        self.results_list.delete(0, tk.END)
        if not self.index:
            messagebox.showwarning("No index", "Please Extract first.")
            return
        key = self.query_var.get().strip()
        if not key:
            return
        hits = search_files(self.index, key)
        if hits:
            for m in hits:
                self.results_list.insert(tk.END, f"./Jan/{Path(m).name}")
        else:
            self.results_list.insert(tk.END, "no match")


if __name__ == "__main__":
    app = MySearchGUI()
    app.mainloop()
