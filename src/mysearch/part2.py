# src/mysearch/part2.py
"""
Part 2 — Indexer + Search
Matches Part 1's two-pane layout:
  Left: zip pick + Build Index + Indexed files
  Right: query box + Search button + Matches (names only)

Notes
- Does NOT auto-build on open (you chose manual Build Index).
- Uses Jan.zip if no file is selected.
"""

from typing import Set
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .part2_core import (
    build_index_from_zip,
    boolean_or,
    boolean_and,
    boolean_but,
    phrase_search,
    vector_rank,
)

class Part2Tab:
    def __init__(self, parent: ttk.Frame):
        # outer
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        # Zip selection row (same vibe as Part 1)
        zip_row = ttk.Frame(outer)
        zip_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(zip_row, text="Zip selection:").pack(side=tk.LEFT)
        ttk.Button(zip_row, text="Open…", command=self._on_open_zip).pack(side=tk.LEFT, padx=8)
        self.zip_name_var = tk.StringVar(value="File name: No file selected (will use Jan.zip)")
        ttk.Label(zip_row, textvariable=self.zip_name_var).pack(side=tk.LEFT, padx=8)
        ttk.Button(zip_row, text="Use Default (Jan.zip)", command=self._use_default_zip).pack(side=tk.RIGHT)

        ttk.Separator(outer, orient="horizontal").pack(fill=tk.X, pady=6)

        # Two columns
        two_col = ttk.Frame(outer)
        two_col.pack(fill=tk.BOTH, expand=True)

        # Left column — Indexing
        left = ttk.Frame(two_col, padding=(0, 0, 12, 0))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(left, text="Indexer", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Button(left, text="Build Index", command=self._on_build_index).pack(anchor="w", pady=(6, 6))

        # Indexed files list (names only)
        lf = ttk.LabelFrame(left, text="Indexed files")
        lf.pack(fill=tk.BOTH, expand=True)
        self.files_list = tk.Listbox(lf, height=25)
        yscroll1 = ttk.Scrollbar(lf, orient="vertical", command=self.files_list.yview)
        self.files_list.configure(yscrollcommand=yscroll1.set)
        self.files_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll1.pack(side=tk.RIGHT, fill=tk.Y)

        self.summary_var = tk.StringVar(value="No index yet.")
        ttk.Label(left, textvariable=self.summary_var).pack(anchor="w", pady=(6, 0))

        # Vertical separator
        ttk.Separator(two_col, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=4)

        # Right column — Key Search (names only results)
        right = ttk.Frame(two_col, padding=(12, 0, 0, 0))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Key Search", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        qrow = ttk.Frame(right)
        qrow.pack(fill=tk.X, pady=(6, 6))
        ttk.Label(qrow, text="Search key:").pack(side=tk.LEFT)
        self.query_var = tk.StringVar()
        ent = ttk.Entry(qrow, textvariable=self.query_var, width=28)
        ent.pack(side=tk.LEFT, padx=8)
        ent.bind("<Return>", lambda e: self._on_search())
        ttk.Button(qrow, text="Search", command=self._on_search).pack(side=tk.LEFT)

        rf = ttk.LabelFrame(right, text="Matches")
        rf.pack(fill=tk.BOTH, expand=True)
        self.results_list = tk.Listbox(rf, height=25)
        yscroll2 = ttk.Scrollbar(rf, orient="vertical", command=self.results_list.yview)
        self.results_list.configure(yscrollcommand=yscroll2.set)
        self.results_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll2.pack(side=tk.RIGHT, fill=tk.Y)

        # internal state
        self.selected_zip_path: str | None = None
        self.inv = None  # InvertedIndex (from part2_core)

    # ---- required by plugin loader ----
    def widget(self):
        # gui.py calls build_tab(parent) which returns this container
        return self._get_root()

    def _get_root(self):
        # The outermost frame we packed in __init__ is parent.winfo_children()[0]
        # but since we keep references, simply return the top-level via traversing results_list
        # which sits under the same outer. Simpler: walk up to the top master Frame.
        # In practice, returning the parent passed to build_tab is enough;
        # but we expose this method for clarity and future adjustments.
        return self.results_list.nametowidget(self.results_list.winfo_parent()).nametowidget(
            self.results_list.nametowidget(self.results_list.winfo_parent()).winfo_parent()
        )

    # ---- UI callbacks ----
    def _on_open_zip(self):
        path = filedialog.askopenfilename(
            title="Select dataset zip",
            filetypes=[("Zip files", "*.zip")],
        )
        if not path:
            return
        self.selected_zip_path = path
        self.zip_name_var.set(f"File name: {path.split('/')[-1] or path.split('\\\\')[-1]}")
        self._clear_lists()

    def _use_default_zip(self):
        self.selected_zip_path = None
        self.zip_name_var.set("File name: No file selected (will use Jan.zip)")
        self._clear_lists()

    def _on_build_index(self):
        try:
            path = self.selected_zip_path or "Jan.zip"
            self.inv = build_index_from_zip(path)
        except FileNotFoundError as e:
            messagebox.showerror("Zip not found", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build index: {e}")
            return

        # populate files list (names only)
        self.files_list.delete(0, tk.END)
        for d in sorted(self.inv.docs.keys()):
            self.files_list.insert(tk.END, f"./Jan/{self.inv.docs[d].path.split('/')[-1]}")

        self.summary_var.set(f"Indexed {self.inv.N} files.")

    def _on_search(self):
        self.results_list.delete(0, tk.END)
        if not self.inv:
            messagebox.showwarning("No index", "Please Build Index first.")
            return

        q = self.query_var.get().strip()
        if not q:
            return

        # Phrase query if wrapped in quotes
        if q.startswith('"') and q.endswith('"') and len(q) > 1:
            hits = phrase_search(self.inv, q[1:-1])
            self._dump_names(hits)
            return

        toks = q.lower().split()
        if "or" in toks:
            terms = [t for t in toks if t != "or"]
            hits = boolean_or(self.inv, terms)
            self._dump_names(hits)
            return
        if "and" in toks:
            terms = [t for t in toks if t != "and"]
            hits = boolean_and(self.inv, terms)
            self._dump_names(hits)
            return
        if "but" in toks:
            i = toks.index("but")
            left, right = toks[:i], toks[i + 1 :]
            hits = boolean_but(self.inv, left, right)
            self._dump_names(hits)
            return

        # Free-text vector ranking (names only)
        ranked = vector_rank(self.inv, q, topk=50)
        if not ranked:
            self.results_list.insert(tk.END, "no match")
        else:
            for d, _score in ranked:
                self.results_list.insert(tk.END, f"./Jan/{self.inv.docs[d].path.split('/')[-1]}")

    # ---- helpers ----
    def _dump_names(self, docs: Set[int]):
        if not docs:
            self.results_list.insert(tk.END, "no match")
            return
        for d in sorted(docs):
            self.results_list.insert(tk.END, f"./Jan/{self.inv.docs[d].path.split('/')[-1]}")

    def _clear_lists(self):
        self.files_list.delete(0, tk.END)
        self.results_list.delete(0, tk.END)
        self.summary_var.set("Ready to build index.")

def build_tab(parent):
    # Create and mount the tab’s UI into the parent, and return the container.
    tab = Part2Tab(parent)
    # In our layout, returning 'parent' itself is correct because we packed into it.
    return parent
