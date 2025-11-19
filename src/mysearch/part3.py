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
import threading


from .part3_spider import (
    build_index_from_spider,
    extract_zip_to_temp,
    open_local_in_browser,
    boolean_or,
    boolean_and,
    boolean_but,
    phrase_search,
    vector_rank,
    WORD_RE,
    make_snippet,
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

        # ---- Two columns (resizable) ----
        split = tk.PanedWindow(self.frame, orient="horizontal", sashwidth=5)
        split.pack(fill="both", expand=True)

        left = ttk.Frame(split, padding=(0, 0, 6, 0))
        right = ttk.Frame(split, padding=(6, 0, 0, 0))

        # Add panes with weights (relative resize) and a minimum size for the left pane
        split.add(left, minsize=260)
        split.add(right, minsize=340)

        # Set initial sash position AFTER layout so 'winfo_width' is valid.
        def _init_sash():
            try:
                total = split.winfo_width()
                if total <= 1:
                    self.frame.after(50, _init_sash)
                    return
                split.sashpos(0, int(total * 0.42))
            except Exception:
                pass
        self.frame.after_idle(_init_sash)


        # Left: spider and file list
        ttk.Label(left, text="Spider + Index", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._crawl_btn = ttk.Button(left, text="Crawl and Build Index", command=self._crawl_build_async)
        self._crawl_btn.pack(anchor="w", pady=(4,6))

        lf = ttk.LabelFrame(left, text="Crawled files")
        lf.pack(fill="both", expand=True)
        self.file_list = tk.Listbox(lf, height=24)
        self.file_list.pack(fill="both", expand=True)
        self.file_list.bind("<Double-Button-1>", self._open_from_left)

        # Right: query UI
        ttk.Label(right, text="Search", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        qrow = ttk.Frame(right); qrow.pack(fill="x", pady=(4,6))
        ttk.Label(qrow, text="Search key:").pack(side="left")
        self.qvar = tk.StringVar()
        self.entry = ttk.Entry(qrow, textvariable=self.qvar, width=48)
        self.entry.pack(side="left", padx=6)
        self.entry.bind("<Return>", lambda e: self._run_query())
        ttk.Button(qrow, text="Search", command=self._run_query).pack(side="left")

        # NEW: docs matched counter
        self.match_var = tk.StringVar(value="Docs matched: 0")
        ttk.Label(qrow, textvariable=self.match_var).pack(side="left", padx=(10, 0))

        rf = ttk.LabelFrame(right, text="Matches (double-click to open)")
        rf.pack(fill="both", expand=True)
        self.results = tk.Listbox(rf, height=24)
        self.results.pack(fill="both", expand=True)
        self.results.bind("<Double-Button-1>", self._open_hit)
        self._result_docids: list[int] = []

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

    def _crawl_build_async(self):
        """Start crawl/index in a worker thread and show a modal progress dialog."""
        # Progress dialog (modal)
        self._prog = tk.Toplevel(self.frame)
        self._prog.title("Building index…")
        self._prog.transient(self.frame.winfo_toplevel())
        self._prog.grab_set()  # modal
        ttk.Label(self._prog, text="Crawling and indexing rhf.zip…").pack(padx=12, pady=(12, 6))
        self._pb = ttk.Progressbar(self._prog, mode="indeterminate", length=260)
        self._pb.pack(padx=12, pady=(0, 12))
        self._pb.start(10)

        # Disable the button while running
        try:
            self._crawl_btn.state(["disabled"])
        except Exception:
            pass

        # Kick off worker thread
        t = threading.Thread(target=self._crawl_build_worker, daemon=True)
        t.start()

    def _crawl_build_worker(self):
        """Background thread: do the heavy work, then hand results back to the UI thread."""
        try:
            path = self.zip_path or "rhf.zip"
            inv, from_cache = build_index_from_spider(path, start="rhf/index.html", use_cache=True)
            tmp_root = extract_zip_to_temp(path)
            # hand off to main thread
            self.frame.after(0, lambda: self._crawl_build_done(inv=inv, tmp_root=tmp_root, from_cache=from_cache))
        except Exception as e:
            self.frame.after(0, lambda: self._crawl_build_done(error=e))

    def _crawl_build_done(self, inv=None, tmp_root=None, from_cache=False, error=None):
        """UI thread: close dialog, update widgets, show message."""
        # Close progress dialog
        try:
            if hasattr(self, "_pb"):
                self._pb.stop()
            if hasattr(self, "_prog") and self._prog.winfo_exists():
                self._prog.grab_release()
                self._prog.destroy()
        except Exception:
            pass

        # Re-enable button
        try:
            self._crawl_btn.state(["!disabled"])
        except Exception:
            pass

        if error is not None:
            messagebox.showerror("Error", str(error))
            return

        # Update state/UI
        self.inv = inv
        self.tmp_root = tmp_root

        self.results.delete(0, "end")
        self.file_list.delete(0, "end")
        self.match_var.set("Docs matched: 0")
        self._result_docids.clear()

        for d in sorted(self.inv.docs):
            self.file_list.insert("end", self.inv.docs[d].path.strip("./"))

        self.qvar.set("")
        self.entry.focus_set()

        msg = f"Indexed {self.inv.N} pages."
        if from_cache:
            pass
        messagebox.showinfo("Spider complete", msg)

    def _crawl_build(self):
        """Run the spider and build the index, then list files."""
        self.results.delete(0, "end")
        self.file_list.delete(0, "end")
        self.match_var.set("Docs matched: 0")  # reset counter
        self._result_docids.clear()
        try:
            path = self.zip_path or "rhf.zip"
            self.inv, from_cache = build_index_from_spider(path, start="rhf/index.html", use_cache=True)
            self.tmp_root = extract_zip_to_temp(path)
            for d in sorted(self.inv.docs):
                self.file_list.insert("end", self.inv.docs[d].path.strip("./"))
            # Ready for searching
            self.qvar.set("")
            self.entry.focus_set()
            msg = f"Indexed {self.inv.N} pages."
            if from_cache:
                msg += " (loaded from cache)"
            messagebox.showinfo("Spider complete", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _run_query(self):
        """Handle Boolean, phrase (quoted), or ranked search."""
        self.results.delete(0, "end")
        self._result_docids.clear()
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
        terms = {m.group(0).lower() for m in WORD_RE.finditer(q)}

        for d, score in ranked:
            doc = self.inv.docs[d]
            rel = doc.path.strip("./")
            title = doc.title or rel
            snippet = make_snippet(doc.text, terms)
            if snippet:
                line = f"{score:0.4f}  {title} — {rel}    {snippet}"
            else:
                line = f"{score:0.4f}  {title} — {rel}"
            self.results.insert("end", line)
            self._result_docids.append(d)

    def _show(self, docs: Set[int]):
        """Render a set of doc ids and update the counter (with title/snippet)."""
        self._result_docids.clear()
        if not docs:
            self.results.insert("end", "no match")
            self.match_var.set("Docs matched: 0")
            return

        self.match_var.set(f"Docs matched: {len(docs)}")
        q = self.qvar.get().strip()
        terms = {m.group(0).lower() for m in WORD_RE.finditer(q)}

        for d in sorted(docs):
            doc = self.inv.docs[d]
            rel = doc.path.strip("./")
            title = doc.title or rel
            snippet = make_snippet(doc.text, terms)
            line = f"{title} — {rel}" + (f"    {snippet}" if snippet else "")
            self.results.insert("end", line)
            self._result_docids.append(d)
    def _open_from_left(self, event=None):
        """Open the double-clicked item from the left crawled-files list."""
        if not self.tmp_root:
            return
        sel = self.file_list.curselection()
        if not sel:
            return
        rel = self.file_list.get(sel[0])
        open_local_in_browser(self.tmp_root, rel)

    def _open_hit(self, event=None):
        """Open the selected result in the default browser."""
        if not self.tmp_root:
            return
        sel = self.results.curselection()
        if not sel:
            return
        row = sel[0]
        if row >= len(self._result_docids):
            return
        d = self._result_docids[row]
        rel = self.inv.docs[d].path.strip("./")
        open_local_in_browser(self.tmp_root, rel)

def build_tab(parent):
    ui = Part3Tab(parent)
    ui.frame.pack(fill="both", expand=True)
    return ui.frame
