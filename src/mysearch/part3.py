# src/mysearch/part3.py
"""
Part 3 GUI — Spider + Search

Actions
- Pick rhf.zip (or use default in project root)
- Crawl and build the index
- Run Boolean, Phrase, or Ranked queries
- Double-click a result to open the HTML in the browser
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Set

from .part3_spider import (
    build_index_from_spider,
    extract_zip_to_temp,
    open_local_in_browser,
    boolean_or,
    boolean_and,
    boolean_but,
    phrase_search,
    vector_rank,
)

class Part3Tab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=8)

        # Keep paths and the index here
        self.zip_path: str | None = None
        self.tmp_root: str | None = None
        self.inv = None

        # ---- Top bar: choose ZIP ----
        top = ttk.Frame(self.frame); top.pack(fill="x", pady=(0,8))
        ttk.Label(top, text="Zip selection:").pack(side="left")
        ttk.Button(top, text="Open...", command=self._pick_zip).pack(side="left", padx=(6,0))
        self.zlabel = ttk.Label(top, text="No file selected (expects rhf.zip)")
        self.zlabel.pack(side="left", padx=8)
        ttk.Button(top, text="Use rhf.zip in project root", command=self._use_default).pack(side="right")

        # ---- Two columns ----
        main = ttk.Frame(self.frame); main.pack(fill="both", expand=True)
        left = ttk.Frame(main);  left.pack(side="left", fill="both", expand=True, padx=(0,6))
        right = ttk.Frame(main); right.pack(side="left", fill="both", expand=True, padx=(6,0))

        # Left: spider and file list
        ttk.Label(left, text="Spider + Index", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Button(left, text="Crawl and Build Index", command=self._crawl_build).pack(anchor="w", pady=(4,6))

        lf = ttk.LabelFrame(left, text="Crawled files")
        lf.pack(fill="both", expand=True)
        self.file_list = tk.Listbox(lf, height=24)
        self.file_list.pack(fill="both", expand=True)

        # Right: query UI
        ttk.Label(right, text="Search", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        qrow = ttk.Frame(right); qrow.pack(fill="x", pady=(4,6))
        ttk.Label(qrow, text="Search key:").pack(side="left")
        self.qvar = tk.StringVar()
        ent = ttk.Entry(qrow, textvariable=self.qvar, width=48)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda e: self._run_query())
        ttk.Button(qrow, text="Search", command=self._run_query).pack(side="left")

        # NEW: docs matched counter
        self.match_var = tk.StringVar(value="Docs matched: 0")
        ttk.Label(qrow, textvariable=self.match_var).pack(side="left", padx=(10, 0))

        rf = ttk.LabelFrame(right, text="Matches (double-click to open)")
        rf.pack(fill="both", expand=True)
        self.results = tk.Listbox(rf, height=24)
        self.results.pack(fill="both", expand=True)
        self.results.bind("<Double-Button-1>", self._open_hit)

        ttk.Label(
            self.frame,
            text='Examples:  cat or dog   |   cat and dog   |   cat but dog   |   "information retrieval"   |   credit card',
            foreground="#666",
        ).pack(fill="x", pady=(6,0))

    def widget(self):
        return self.frame

    # ---- callbacks ----

    def _pick_zip(self):
        p = filedialog.askopenfilename(title="Select rhf.zip", filetypes=[("Zip files","*.zip")])
        if p:
            self.zip_path = p
            self.zlabel.config(text=p)

    def _use_default(self):
        self.zip_path = "rhf.zip"
        self.zlabel.config(text="Using rhf.zip in project root")
        
    def _crawl_build(self):
        """Run the spider and build the index, then list files."""
        self.results.delete(0, "end")
        self.file_list.delete(0, "end")
        self.match_var.set("Docs matched: 0")  # reset counter
        try:
            path = self.zip_path or "rhf.zip"
            self.inv = build_index_from_spider(path, start="rhf/index.html")
            self.tmp_root = extract_zip_to_temp(path)
            for d in sorted(self.inv.docs):
                self.file_list.insert("end", self.inv.docs[d].path.strip("./"))
            messagebox.showinfo("Spider complete", f"Indexed {self.inv.N} reachable pages.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _run_query(self):
        """Handle Boolean, phrase (quoted), or ranked search."""
        self.results.delete(0, "end")
        if not self.inv:
            self.results.insert("end", "Build the index first")
            self.match_var.set("Docs matched: 0")
            return
        q = self.qvar.get().strip()
        if not q:
            self.match_var.set("Docs matched: 0")
            return

        # Phrase search if fully quoted
        if q.startswith('"') and q.endswith('"') and len(q) > 1:
            docs = phrase_search(self.inv, q[1:-1])
            return self._show(docs)

        # Strict Boolean: look for the connector words
        toks = q.lower().split()
        if "or" in toks:
            terms = [t for t in toks if t != "or"]
            return self._show(boolean_or(self.inv, terms))
        if "and" in toks:
            terms = [t for t in toks if t != "and"]
            return self._show(boolean_and(self.inv, terms))
        if "but" in toks:
            i = toks.index("but"); left=toks[:i]; right=toks[i+1:]
            return self._show(boolean_but(self.inv, left, right))

        # Otherwise free text ranking
        ranked = vector_rank(self.inv, q, topk=50)
        if not ranked:
            self.results.insert("end", "no match")
            self.match_var.set("Docs matched: 0")
            return
        self.match_var.set(f"Docs matched: {len(ranked)}")
        for d, score in ranked:
            self.results.insert("end", f"{score:0.4f}  {self.inv.docs[d].path.strip('./')}")

    def _show(self, docs: Set[int]):
        """Render a set of doc ids and update the counter."""
        if not docs:
            self.results.insert("end", "no match")
            self.match_var.set("Docs matched: 0")
            return
        self.match_var.set(f"Docs matched: {len(docs)}")
        for d in sorted(docs):
            self.results.insert("end", self.inv.docs[d].path.strip("./"))

    def _open_hit(self, event=None):
        """Open the selected result in the default browser."""
        if not self.tmp_root:
            return
        sel = self.results.curselection()
        if not sel:
            return
        line = self.results.get(sel[0])
        rel = line.split()[-1]  # works for both "score path" and "path"
        open_local_in_browser(self.tmp_root, rel)

def build_tab(parent):
    ui = Part3Tab(parent)
    ui.frame.pack(fill="both", expand=True)
    return ui.frame
