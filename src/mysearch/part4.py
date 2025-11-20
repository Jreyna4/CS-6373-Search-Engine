# src/mysearch/part4.py
"""
Part 4 GUI: Query Reformulation on top of the spider index (rhf.zip).

Workflow
--------
- Build the index from rhf.zip using the same spider as Part 3.
- User types an original query.
- We call reformulate_and_search() from part4_core, which:
    * gets initial ranked results S
    * uses top docs for pseudo relevance feedback
    * computes correlated expansion terms
    * runs expanded query to get S'
- GUI shows:
    * Expanded query string
    * Added terms
    * Results list with color coding:
        - blue items: docs from original S
        - green items: docs that appear only in S'
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Set

from .part3_spider import (
    build_index_from_spider,
    extract_zip_to_temp,
    open_local_in_browser,
)
from .part4_core import reformulate_and_search


class Part4Tab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=8)

        self.zip_path: str | None = None
        self.tmp_root: str | None = None
        self.inv = None  # InvertedIndex from part3_spider

        # ---------------- Top bar: zip selection ----------------
        top = ttk.Frame(self.frame)
        top.pack(fill="x", pady=(0, 8))

        ttk.Label(top, text="Zip selection:").pack(side="left")
        ttk.Button(top, text="Open...", command=self._pick_zip).pack(side="left", padx=(6, 0))
        self.zlabel = ttk.Label(top, text="No file selected (expects rhf.zip)")
        self.zlabel.pack(side="left", padx=8)
        ttk.Button(top, text="Use rhf.zip in project root", command=self._use_default).pack(
            side="right"
        )

        # ---------------- Main split: left status, right query ----------------
        main = ttk.Frame(self.frame)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        # Left: index status
        ttk.Label(left, text="Indexer status", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Button(
            left,
            text="Build Index from rhf.zip",
            command=self._build_index,
        ).pack(anchor="w", pady=(4, 6))

        self.status = tk.Text(left, width=50, height=24)
        self.status.pack(fill="both", expand=True)
        self._log_status("No index yet. Click 'Build Index from rhf.zip' to start.\n")

        # Right: query and results
        ttk.Label(right, text="Query Reformulation", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )

        # Original query row
        qrow = ttk.Frame(right)
        qrow.pack(fill="x", pady=(4, 4))
        ttk.Label(qrow, text="Original query:").pack(side="left")
        self.qvar = tk.StringVar()
        ent = ttk.Entry(qrow, textvariable=self.qvar, width=48)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda e: self._run_reformulated())
        ttk.Button(qrow, text="Run", command=self._run_reformulated).pack(side="left")

        # Expanded query + added terms
        info = ttk.Frame(right)
        info.pack(fill="x", pady=(4, 4))

        self.expanded_var = tk.StringVar(value="Expanded query: (not run yet)")
        ttk.Label(info, textvariable=self.expanded_var, wraplength=420, justify="left").pack(
            anchor="w"
        )

        self.terms_var = tk.StringVar(value="Added terms: (none)")
        ttk.Label(info, textvariable=self.terms_var, foreground="#444").pack(
            anchor="w",
            pady=(2, 0),
        )

        # Results list
        rf = ttk.LabelFrame(right, text="Results (blue = original S, green = new in S')")
        rf.pack(fill="both", expand=True, pady=(4, 0))

        self.results = tk.Listbox(rf, height=24)
        self.results.pack(fill="both", expand=True)
        self.results.bind("<Double-Button-1>", self._open_hit)

        self.count_var = tk.StringVar(value="Docs matched: 0 (S = 0, S' only = 0)")
        ttk.Label(right, textvariable=self.count_var).pack(anchor="w", pady=(4, 0))

        # Footer hint
        ttk.Label(
            self.frame,
            text=(
                "Tip: try queries like  credit card   or   information retrieval   "
                "and see what extra terms are used."
            ),
            foreground="#666",
        ).pack(fill="x", pady=(6, 0))

    # ---------------- helpers ----------------

    def widget(self):
        return self.frame

    def _log_status(self, msg: str):
        self.status.insert("end", msg)
        self.status.see("end")

    # ---------------- callbacks ----------------

    def _pick_zip(self):
        p = filedialog.askopenfilename(title="Select rhf.zip", filetypes=[("Zip files", "*.zip")])
        if p:
            self.zip_path = p
            self.zlabel.config(text=p)

    def _use_default(self):
        self.zip_path = "rhf.zip"
        self.zlabel.config(text="Using rhf.zip in project root")

    def _build_index(self):
        """Reuse the spider from Part 3 to build the index for Part 4."""
        self.status.delete("1.0", "end")
        try:
            path = self.zip_path or "rhf.zip"
            self._log_status(f"Building index from {path} ...\n")

            # unpack (inv, from_cache)
            self.inv, from_cache = build_index_from_spider(
                path,
                start="rhf/index.html",
                use_cache=True,
            )

            # extract zip so we can open pages on double-click
            self.tmp_root = extract_zip_to_temp(path)

            msg = f"Indexed {self.inv.N} reachable pages."
            if from_cache:
                msg += " (loaded from cache)"
            self._log_status(msg + "\n")

        except Exception as e:
            messagebox.showerror("Error building index", str(e))


    def _run_reformulated(self):
        """Run query reformulation and display S and S' with color coding."""
        self.results.delete(0, "end")
        if not self.inv:
            self.results.insert("end", "Build the index first.")
            return

        q = self.qvar.get().strip()
        if not q:
            return

        expanded_q, added, ranked_S, ranked_Sp = reformulate_and_search(self.inv, q)

        if not ranked_S:
            self.results.insert("end", "No documents matched the original query.")
            self.expanded_var.set("Expanded query: (no matches)")
            self.terms_var.set("Added terms: (none)")
            self.count_var.set("Docs matched: 0 (S = 0, S' only = 0)")
            return

        # Update labels
        self.expanded_var.set(f"Expanded query: {expanded_q}")
        if added:
            self.terms_var.set("Added terms: " + ", ".join(added))
        else:
            self.terms_var.set("Added terms: (none, used original query)")

        # Build sets for color coding
        S_docs: Set[int] = {d for d, _ in ranked_S}
        Sp_docs: Set[int] = {d for d, _ in ranked_Sp}

        shown = 0
        only_Sp_count = 0
        for doc_id, score in ranked_Sp:
            path = self.inv.docs[doc_id].path.strip("./")
            label = f"{score:0.4f}  {path}"

            idx = self.results.size()
            self.results.insert("end", label)

            if doc_id in S_docs:
                # in both S and S'  -> blue
                self.results.itemconfig(idx, foreground="blue")
            else:
                # new docs from expanded query only -> green
                self.results.itemconfig(idx, foreground="green")
                only_Sp_count += 1

            shown += 1

        self.count_var.set(
            f"Docs matched: {shown} (S = {len(S_docs)}, S' only = {only_Sp_count})"
        )

    def _open_hit(self, event=None):
        """Open the selected result in the default browser (if we have temp files)."""
        if not self.tmp_root:
            return
        sel = self.results.curselection()
        if not sel:
            return
        line = self.results.get(sel[0])
        rel = line.split()[-1]  # last token is the relative path
        open_local_in_browser(self.tmp_root, rel)


def build_tab(parent):
    ui = Part4Tab(parent)
    ui.frame.pack(fill="both", expand=True)
    return ui.frame
