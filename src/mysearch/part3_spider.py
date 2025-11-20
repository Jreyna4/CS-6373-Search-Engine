# src/mysearch/part3_spider.py
"""
Part 3 spider + indexer.

Responsibilities
- Open rhf.zip (or another zip of HTML files)
- Build an inverted index over all HTML pages
- Cache the built index to speed up later runs
- Provide vector-space ranking for queries
- Provide helpers to extract the zip to a temp folder and open pages in a browser

Important:
- build_index_from_spider() returns (inv, from_cache)
  so callers must unpack it as: inv, from_cache = build_index_from_spider(...)
"""

from __future__ import annotations

import math
import os
import pickle
import re
import tempfile
import webbrowser
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

from bs4 import BeautifulSoup, Comment


# -------------------------
# Tokenization config
# -------------------------

WORD_RE = re.compile(r"[A-Za-z']+")

STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "to", "for", "from",
    "by", "with", "about", "as", "at", "into", "through", "during", "before",
    "after", "above", "below", "under", "over", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can",
    "will", "just", "don", "should", "now", "is", "are", "was", "were", "be",
    "been", "being", "it", "its", "that", "this", "these", "those", "he", "she",
    "they", "them", "we", "you", "i", "me", "my", "our", "your", "their", "his",
    "her", "who", "whom", "which", "what"
}


# -------------------------
# Core index data structures
# -------------------------

@dataclass
class Posting:
    tf: int = 0
    positions: List[int] = field(default_factory=list)
    tfidf: float = 0.0


@dataclass
class DocMeta:
    doc_id: int
    path: str
    length_in_terms: int = 0
    outlinks: List[str] = field(default_factory=list)
    vector_norm: float = 0.0


class InvertedIndex:
    """
    term -> {doc_id -> Posting}
    df   -> term document frequency
    docs -> doc_id -> DocMeta
    """
    def __init__(self) -> None:
        self.index: Dict[str, Dict[int, Posting]] = {}
        self.df: Dict[str, int] = {}
        self.docs: Dict[int, DocMeta] = {}
        self.path_to_id: Dict[str, int] = {}
        self.N: int = 0
        self._idf: Dict[str, float] = {}

    def add_document(self, doc_id: int, path: str,
                     tokens: List[str], outlinks: List[str]) -> None:
        self.docs[doc_id] = DocMeta(
            doc_id=doc_id,
            path=path,
            length_in_terms=len(tokens),
            outlinks=outlinks,
        )
        self.path_to_id[path] = doc_id

        positions_by_term: Dict[str, List[int]] = {}
        for pos, tok in enumerate(tokens):
            positions_by_term.setdefault(tok, []).append(pos)

        for term, positions in positions_by_term.items():
            postings = self.index.setdefault(term, {})
            if doc_id not in postings:
                postings[doc_id] = Posting(tf=len(positions),
                                           positions=positions)
                self.df[term] = self.df.get(term, 0) + 1
            else:
                p = postings[doc_id]
                p.positions.extend(positions)
                p.tf += len(positions)

    def finalize(self) -> None:
        """Compute tf-idf weights and document vector norms."""
        self.N = len(self.docs)
        if self.N == 0:
            return

        # idf for all terms
        self._idf = {
            t: math.log10(self.N / df) if df > 0 else 0.0
            for t, df in self.df.items()
        }

        # accumulate squared norms
        sq_sum: Dict[int, float] = {d: 0.0 for d in self.docs}
        for term, postings in self.index.items():
            idf = self._idf[term]
            for d, post in postings.items():
                tfw = 1.0 + math.log10(post.tf) if post.tf > 0 else 0.0
                w = tfw * idf
                post.tfidf = w
                sq_sum[d] += w * w

        for d, s in sq_sum.items():
            self.docs[d].vector_norm = math.sqrt(s)

    def postings(self, term: str) -> Dict[int, Posting]:
        return self.index.get(term, {})

    def idf(self, term: str) -> float:
        return self._idf.get(term, 0.0)


# -------------------------
# HTML parsing helpers
# -------------------------

def _clean_html_to_text_and_links(raw: bytes) -> Tuple[str, List[str]]:
    soup = BeautifulSoup(raw, "html.parser")

    # remove scripts, styles, and comments
    for s in soup.find_all(["script", "style"]):
        s.extract()
    for c in soup(text=lambda it: isinstance(it, Comment)):
        c.extract()

    text = soup.get_text(separator=" ")
    links = [a["href"] for a in soup.find_all("a", href=True)]
    return text, links


def _tokenize(text: str) -> List[str]:
    raw = (m.group(0).lower() for m in WORD_RE.finditer(text))
    return [t for t in raw if t.strip("'") and t.strip("'") not in STOPWORDS]


# -------------------------
# Caching helpers
# -------------------------

def _zip_signature(zip_path: str) -> str:
    p = Path(zip_path)
    st = p.stat()
    return f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}"


def _cache_file_for(zip_path: str) -> Path:
    sig = _zip_signature(zip_path)
    cache_root = Path(".cache")
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root / f"part3_index_{Path(zip_path).name}_{sig}.pkl"


# -------------------------
# Spider + index builder
# -------------------------

def build_index_from_spider(
    zip_path: str,
    start: str = "rhf/index.html",  # kept for API compatibility, not critical
    use_cache: bool = True,
) -> Tuple[InvertedIndex, bool]:
    """
    Build an inverted index from all HTML files inside the zip.

    Returns (inv, from_cache) so callers can display a cache message.
    """

    cache_file = _cache_file_for(zip_path)
    if use_cache and cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                inv: InvertedIndex = pickle.load(f)
            return inv, True
        except Exception:
            # ignore corrupted cache and rebuild
            cache_file.unlink(missing_ok=True)

    inv = InvertedIndex()

    with zipfile.ZipFile(zip_path, "r") as zf:
        html_files = [
            name for name in zf.namelist()
            if name.lower().endswith((".html", ".htm"))
        ]

        # Simple "spider": index every HTML file in the archive.
        # This guarantees N is the number of pages in rhf.zip,
        # typically in the thousands, not 1.
        for doc_id, name in enumerate(html_files):
            raw = zf.read(name)
            text, links = _clean_html_to_text_and_links(raw)
            tokens = _tokenize(text)
            if not tokens:
                continue
            inv.add_document(doc_id, name, tokens, links)

    inv.finalize()

    if use_cache:
        try:
            with cache_file.open("wb") as f:
                pickle.dump(inv, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            # caching is best effort: do not crash if it fails
            pass

    return inv, False


# -------------------------
# Vector-space ranking
# -------------------------

def vector_rank(inv: InvertedIndex, query: str, topk: int = 40) -> List[Tuple[int, float]]:
    terms = _tokenize(query)
    if not terms:
        return []

    # query tf
    q_tf: Dict[str, int] = {}
    for t in terms:
        if t in inv.df:
            q_tf[t] = q_tf.get(t, 0) + 1
    if not q_tf:
        return []

    # query weights
    q_w: Dict[str, float] = {}
    for t, rtf in q_tf.items():
        tfw = 1.0 + math.log10(rtf)
        q_w[t] = tfw * inv.idf(t)

    q_norm = math.sqrt(sum(w * w for w in q_w.values())) or 1.0
    for t in list(q_w.keys()):
        q_w[t] /= q_norm

    scores: Dict[int, float] = {}
    for t, qw in q_w.items():
        for d, post in inv.postings(t).items():
            dn = inv.docs[d].vector_norm or 1.0
            scores[d] = scores.get(d, 0.0) + (post.tfidf / dn) * qw

    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:topk]


# -------------------------
# Zip extraction + browser helper
# -------------------------

def extract_zip_to_temp(zip_path: str) -> str:
    """
    Extract the zip to a temporary directory and return its path.
    The temp folder is not automatically deleted so repeated opens work.
    """
    tmp_dir = tempfile.mkdtemp(prefix="cs6373_rhf_")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp_dir)
    return tmp_dir


def open_local_in_browser(root_dir: str, rel_path: str) -> None:
    """Open a file under root_dir / rel_path in the default web browser."""
    target = Path(root_dir) / rel_path
    if target.exists():
        webbrowser.open(target.as_uri())
