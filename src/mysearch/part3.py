from typing import Set
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .part3_spider import Spider as SpiderIndex
from .part2_core import boolean_and, boolean_or, boolean_but, phrase_search, vector_rank


class Part3Tab:
    def __init__(self, parent: ttk.Frame):
        self._outer = outer = ttk.Frame(parent, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- ZIP selection row ---
        zip_row = ttk.Frame(outer)
        zip_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(zip_row, text="Zip selection:").pack(side=tk.LEFT)
        ttk.Button(zip_row, text="Open…", command=self._on_open_zip).pack(side=tk.LEFT, padx=8)
        self.zip_name_var = tk.StringVar(value="File name: No file selected (will use rhf.zip)")
        ttk.Label(zip_row, textvariable=self.zip_name_var).pack(side=tk.LEFT, padx=8)
        ttk.Button(zip_row, text="Use Default (rhf.zip)", command=self._use_default_zip).pack(side=tk.RIGHT)

        ttk.Separator(outer, orient="horizontal").pack(fill=tk.X, pady=6)

        # --- Two columns: left=index, right=search ---
        two_col = ttk.Frame(outer)
        two_col.pack(fill=tk.BOTH, expand=True)

        # Left column: Indexer
        left = ttk.Frame(two_col, padding=(0, 0, 12, 0))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(left, text="Spider Indexer", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        btn_row = ttk.Frame(left)
        btn_row.pack(anchor="w", pady=(6, 6))
        ttk.Button(btn_row, text="Build Index", command=self._on_build_index).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Show Preview Index", command=self._show_preview).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="Show Full Index", command=self._show_full).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="Show Unique Terms", command=self._show_unique_terms).pack(side=tk.LEFT, padx=8)


        lf = ttk.LabelFrame(left, text="Indexed files")
        lf.pack(fill=tk.BOTH, expand=True)
        self.files_list = tk.Listbox(lf, height=25)
        yscroll1 = ttk.Scrollbar(lf, orient="vertical", command=self.files_list.yview)
        self.files_list.configure(yscrollcommand=yscroll1.set)
        self.files_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll1.pack(side=tk.RIGHT, fill=tk.Y)
        self.summary_var = tk.StringVar(value="No index yet.")
        ttk.Label(left, textvariable=self.summary_var).pack(anchor="w", pady=(6, 0))

        ttk.Separator(two_col, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=4)

        # Right column: Search
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

        # --- internal state ---
        self.selected_zip_path: str | None = None
        self.inv: SpiderIndex | None = None

    # ---- required by plugin loader ----
    def widget(self):
        return self._outer

    # ---- ZIP selection callbacks ----
    def _on_open_zip(self):
        path = filedialog.askopenfilename(title="Select rhf.zip", filetypes=[("Zip files", "*.zip")])
        if not path:
            return
        self.selected_zip_path = path
        self.zip_name_var.set(f"File name: {Path(path).name}")
        self._clear_lists()

    def _use_default_zip(self):
        self.selected_zip_path = None
        self.zip_name_var.set("File name: No file selected (will use rhf.zip)")
        self._clear_lists()

    # ---- Build Index ----
    def _on_build_index(self):
        try:
            path = self.selected_zip_path or "rhf.zip"
            self.inv = SpiderIndex(path)
            self.inv.crawl_zip()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build index: {e}")
            return

        self.files_list.delete(0, tk.END)
        for doc_id in sorted(self.inv.docs.keys()):
            self.files_list.insert(tk.END, f"./{Path(self.inv.docs[doc_id].path).name}")

        self.summary_var.set(f"Indexed {self.inv.N} files.")

    # ---- Search callback ----
    def _on_search(self):
        self.results_list.delete(0, tk.END)
        if not self.inv:
            messagebox.showwarning("No index", "Please Build Index first.")
            return

        q = self.query_var.get().strip()
        if not q:
            return

        # Phrase query
        if q.startswith('"') and q.endswith('"') and len(q) > 1:
            hits = phrase_search(self.inv, q[1:-1])
            self._dump_names(hits)
            return

        toks = q.lower().split()
        if "or" in toks:
            hits = boolean_or(self.inv, [t for t in toks if t != "or"])
            self._dump_names(hits)
            return
        if "and" in toks:
            hits = boolean_and(self.inv, [t for t in toks if t != "and"])
            self._dump_names(hits)
            return
        if "but" in toks:
            i = toks.index("but")
            left, right = toks[:i], toks[i + 1 :]
            hits = boolean_but(self.inv, left, right)
            self._dump_names(hits)
            return

        # Free-text vector ranking
        ranked = vector_rank(self.inv, q, topk=50)
        if not ranked:
            self.results_list.insert(tk.END, "no match")
        else:
            for d, _ in ranked:
                self.results_list.insert(tk.END, f"./{Path(self.inv.docs[d].path).name}")

    # ---- Helpers ----
    def _dump_names(self, docs: Set[int]):
        if not docs:
            self.results_list.insert(tk.END, "no match")
            return
        for d in sorted(docs):
            self.results_list.insert(tk.END, f"./{Path(self.inv.docs[d].path).name}")

    def _clear_lists(self):
        self.files_list.delete(0, tk.END)
        self.results_list.delete(0, tk.END)
        self.summary_var.set("Ready to build index.")

    # ==============================
    # Debug popups: Preview vs Full
    # ==============================

    def _show_preview(self):
        """Small, fast snapshot: limited terms/postings/positions."""
        if not self.inv:
            messagebox.showwarning("No index", "Please Build Index first.")
            return

        LIMIT_DOCS = 12
        LIMIT_TERMS = 20
        LIMIT_POSTINGS = 6
        LIMIT_POSITIONS = 12

        lines: list[str] = []

        # --- Document table ---
        lines.append("=== Document Table (doc_id -> path, length, norm) ===")
        for doc_id in sorted(self.inv.docs.keys())[:LIMIT_DOCS]:
            info = self.inv.docs[doc_id]
            fname = Path(info.path).name
            lines.append(f"[{doc_id}] ./{fname} (len={info.length}, norm={info.norm:.4f})")
        extra_docs = len(self.inv.docs) - LIMIT_DOCS
        if extra_docs > 0:
            lines.append(f"... and {extra_docs} more document(s)")
        lines.append("")

        # --- Inverted index table ---
        lines.append("=== Inverted Index (term -> {doc_id: (freq, tfidf, positions)}) ===")
        terms = sorted(self.inv.inv.keys())[:LIMIT_TERMS]
        for term in terms:
            lines.append(f"'{term}':")
            postings = self.inv.inv[term]
            c = 0
            for d in sorted(postings.keys()):
                post = postings[d]
                pos_show = post.positions[:LIMIT_POSITIONS]
                pos_str = ", ".join(str(p) for p in pos_show)
                suffix = " ..." if len(post.positions) > LIMIT_POSITIONS else ""
                lines.append(f"    -> Doc {d}: freq={post.freq}, tfidf={post.tfidf:.4f}, positions=[{pos_str}{suffix}]")
                c += 1
                if c >= LIMIT_POSTINGS:
                    left = len(postings) - LIMIT_POSTINGS
                    if left > 0:
                        lines.append(f"    ... and {left} more posting(s)")
                    break

        self._open_text_popup("Spider Index — PREVIEW", lines, w=850, h=620)

    def _show_full(self):
        """Complete dump: all docs, all terms, all postings."""
        if not self.inv:
            messagebox.showwarning("No index", "Please Build Index first.")
            return

        lines: list[str] = []

        # --- Document table ---
        lines.append("=== Document Table (doc_id -> path, length, norm) ===")
        for doc_id in sorted(self.inv.docs.keys()):
            info = self.inv.docs[doc_id]
            fname = Path(info.path).name
            lines.append(f"[{doc_id}] ./{fname} (len={info.length}, norm={info.norm:.4f})")
        lines.append("")

        # --- Full inverted index ---
        lines.append("=== Inverted Index (term -> {doc_id: (freq, tfidf, positions[])}) ===")
        for term in sorted(self.inv.inv.keys()):
            lines.append(f"'{term}':")
            postings = self.inv.inv[term]
            for d in sorted(postings.keys()):
                post = postings[d]
                pos_str = ", ".join(str(p) for p in post.positions)
                lines.append(f"    -> Doc {d}: freq={post.freq}, tfidf={post.tfidf:.4f}, positions=[{pos_str}]")
        lines.append("")

        self._open_text_popup("Spider Index — FULL DUMP", lines, w=980, h=720)

    def _show_unique_terms(self):
        """Show all unique terms in the index."""
        if not self.inv:
            messagebox.showwarning("No index", "Please Build Index first.")
            return

        terms = sorted(self.inv.inv.keys())
        content = "\n".join(terms) if terms else "No terms indexed."
        self._open_text_popup("Unique Terms", content.splitlines())

    # ---- popup builder & clipboard helper (same as Part2Tab) ----
    def _open_text_popup(self, title: str, lines: list[str], w=900, h=700):
        win = tk.Toplevel(self._outer)
        win.title(title)
        win.geometry(f"{int(w)}x{int(h)}")

        controls = ttk.Frame(win)
        controls.pack(fill=tk.X, padx=8, pady=(8, 0))
        ttk.Button(controls, text="Copy to Clipboard", command=lambda: self._copy_to_clipboard("\n".join(lines))).pack(side=tk.LEFT)
        ttk.Button(controls, text="Close", command=win.destroy).pack(side=tk.RIGHT)

        text_frame = ttk.Frame(win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        yscroll = ttk.Scrollbar(text_frame, orient="vertical")
        xscroll = ttk.Scrollbar(text_frame, orient="horizontal")
        txt = tk.Text(
            text_frame,
            wrap="none",
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
            font=("Consolas", 10),
        )
        yscroll.config(command=txt.yview)
        xscroll.config(command=txt.xview)

        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        txt.insert("1.0", "\n".join(lines))
        txt.config(state="disabled")

    def _copy_to_clipboard(self, s: str):
        root = self._outer.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(s)
        root.update()

def build_tab(parent):
    return Part3Tab(parent).widget()
