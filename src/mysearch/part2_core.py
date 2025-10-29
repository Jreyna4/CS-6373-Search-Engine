"""
Core indexing/search logic for Part 2 — Strict Boolean, Phrase, and Vector Search

Implements:
- Task 1: Indexer (tokenization, stopword removal, inverted index with tf-idf + positions)
- Task 2: GUI support (handled in part2.py tab)
- Task 3: Boolean searcher (OR / AND / BUT, strict)
- Task 4: Phrase search (exact adjacency check)
- Vector-space ranking (cosine similarity)

Dataset: Jan.zip (robust zip locator so it works from any working directory and with PyInstaller)
"""

from __future__ import annotations

import re
import sys
import math
import zipfile
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


# ---------------------------
# Inverted Index Data Classes
# ---------------------------

class Posting:
    """Holds positions + term frequency + tf-idf weight for one doc-term pair."""
    def __init__(self, freq=0, positions=None):
        self.freq = freq
        self.positions = positions or []
        self.tfidf = 0.0


class DocInfo:
    """Stores per-document metadata: path and vector length."""
    def __init__(self, path: str = "", length: int = 0):
        self.path = path
        self.length = length
        self.norm = 0.0  # vector norm for cosine similarity


class InvertedIndex:
    """Central inverted index structure."""
    def __init__(self):
        self.docs: Dict[int, DocInfo] = {}             # doc_id -> DocInfo
        self.inv: Dict[str, Dict[int, Posting]] = {}   # term -> {doc_id -> Posting}
        self.df: Dict[str, int] = {}                   # document frequency per term
        self.N: int = 0                                # total docs indexed
        # Task-1: keep hyperlinks for future crawler
        self.links: Dict[int, List[str]] = {}          # doc_id -> list of hrefs found in doc
        self.all_links: Set[str] = set()               # union of all hrefs across docs

    def postings(self, term: str) -> Dict[int, Posting]:
        """Return postings for a term, or empty dict."""
        return self.inv.get(term, {})


# ---------------------------
# Tokenization Utilities
# ---------------------------

STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "but", "to", "in", "on", "for",
    "with", "at", "by", "from", "this", "that", "is", "it", "as"
}

def _norm(term: str) -> str:
    """Normalize tokens (lowercase)."""
    return term.lower()

def tokenize(text: str) -> List[str]:
    # keep letters + apostrophes, lowercase, then drop only edge apostrophes
    raw = re.findall(r"[A-Za-z']+", text)
    toks = []
    for w in raw:
        w = w.lower().strip("'")  # removes quotes at the ends, keeps internal ones
        if w:
            toks.append(w)
    return toks



# ---------------------------
# Robust zip locator (like Part 1)
# ---------------------------

def _candidates_for(zip_name: str):
    """Yield candidate paths to search for the zip."""
    # 1) current working directory and its parents
    cwd = Path.cwd().resolve()
    for p in [cwd, *list(cwd.parents)[:6]]:
        yield p / zip_name
    # 2) this file's directory and its parents
    here = Path(__file__).resolve()
    for p in [here.parent, *list(here.parents)[:6]]:
        yield p / zip_name
    # 3) PyInstaller one-file extraction dir
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            yield Path(sys._MEIPASS) / zip_name  # type: ignore[attr-defined]
        except Exception:
            pass
    # 4) folder containing the frozen executable (one-folder builds)
    if getattr(sys, "frozen", False):
        try:
            yield Path(sys.executable).resolve().parent / zip_name
        except Exception:
            pass

def _resolve_zip(zip_path_or_name: str) -> Path:
    """Return a Path to the zip, resolving names like 'Jan.zip' from common locations."""
    p = Path(zip_path_or_name)
    if p.exists():
        return p
    for cand in _candidates_for(p.name):
        try:
            c = cand.resolve()
        except Exception:
            c = cand
        if c.exists():
            return c
    raise FileNotFoundError(f"[Errno 2] No such file or directory: {p.name!r}")


# ---------------------------
# Index Construction
# ---------------------------

def build_index_from_zip(zip_path: str) -> InvertedIndex:
    """Build an inverted index from a zip of HTML files (robust path resolution)."""
    zp = _resolve_zip(zip_path)

    inv = InvertedIndex()
    with zipfile.ZipFile(zp, "r") as z:
        doc_id = 0
        for name in z.namelist():
            if not name.lower().endswith(".html"):
                continue
            with z.open(name) as f:
                html = f.read().decode(errors="ignore")

            # Extract hyperlinks (simple regex — fine for this dataset)
            hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
            inv.links[doc_id] = hrefs
            inv.all_links.update(hrefs)

            # Strip HTML tags (simple regex-based) and tokenize text
            text = re.sub(r"<[^>]+>", " ", html)
            words = [w for w in tokenize(text) if w not in STOPWORDS]
            if not words:
                continue

            inv.docs[doc_id] = DocInfo(path=f"./{name}", length=len(words))

            # Build postings (freq + positions)
            pos_map = defaultdict(list)
            for i, w in enumerate(words):
                pos_map[w].append(i)

            for w, positions in pos_map.items():
                inv.inv.setdefault(w, {})[doc_id] = Posting(freq=len(positions), positions=positions)

            doc_id += 1

        inv.N = doc_id

    # Document frequencies
    for term, postings in inv.inv.items():
        inv.df[term] = len(postings)

    # Compute tf-idf weights and norms
    for term, postings in inv.inv.items():
        idf = math.log((inv.N) / inv.df[term], 10) if inv.df[term] else 0.0
        for d, post in postings.items():
            post.tfidf = post.freq * idf
            inv.docs[d].norm += post.tfidf ** 2

    for doc in inv.docs.values():
        doc.norm = math.sqrt(doc.norm)

    return inv


# ---------------------------
# Boolean Search (STRICT)
# ---------------------------

def _docset(inv: InvertedIndex, term: str) -> Set[int]:
    return set(inv.postings(_norm(term)).keys())

def boolean_or(inv: InvertedIndex, terms: List[str]) -> Set[int]:
    """Return docs containing ANY of the terms."""
    result = set()
    for t in terms:
        result |= _docset(inv, t)
    return result

def boolean_and(inv: InvertedIndex, terms: List[str]) -> Set[int]:
    """Return docs containing ALL terms (strict AND)."""
    terms = [t for t in terms if t]
    if not terms:
        return set()
    terms_sorted = sorted((_norm(t) for t in terms), key=lambda x: len(inv.postings(x)))
    first = terms_sorted[0]
    first_postings = inv.postings(first)
    if not first_postings:
        return set()
    result = set(first_postings.keys())
    for t in terms_sorted[1:]:
        pst = inv.postings(t)
        if not pst:
            return set()
        result &= set(pst.keys())
        if not result:
            return set()
    return result

def boolean_but(inv: InvertedIndex, left: List[str], right: List[str]) -> Set[int]:
    """Return docs with LEFT terms but excluding RIGHT terms."""
    return boolean_and(inv, left) - boolean_or(inv, right)


# ---------------------------
# Phrase Search (STRICT)
# ---------------------------

def _adjacent_positions(a: List[int], b: List[int]) -> bool:
    """True if any position in b is exactly +1 after some position in a."""
    i = j = 0
    while i < len(a) and j < len(b):
        target = a[i] + 1
        if b[j] == target:
            return True
        if b[j] < target:
            j += 1
        else:
            i += 1
    return False

def phrase_search(inv: InvertedIndex, phrase: str) -> Set[int]:
    """Find documents containing the exact phrase (case-insensitive)."""
    words = [_norm(w) for w in re.findall(r"[A-Za-z']+", phrase) if w]
    if not words:
        return set()

    cand = boolean_and(inv, words)
    if not cand:
        return set()

    out = set()
    for d in cand:
        pos_lists = [inv.postings(w)[d].positions for w in words]
        ok = True
        for k in range(len(pos_lists) - 1):
            if not _adjacent_positions(pos_lists[k], pos_lists[k + 1]):
                ok = False
                break
        if ok:
            out.add(d)
    return out


# ---------------------------
# Vector Space Ranking (cosine)
# ---------------------------

def vector_rank(inv: InvertedIndex, query: str, topk: int = 30) -> List[Tuple[int, float]]:
    """Rank documents by cosine similarity against query vector."""
    terms = [_norm(w) for w in re.findall(r"[A-Za-z']+", query) if w not in STOPWORDS]
    if not terms:
        return []

    # Query term frequencies
    qtf = defaultdict(int)
    for t in terms:
        qtf[t] += 1

    qvec = {}
    for t, f in qtf.items():
        if t in inv.df:
            idf = math.log((inv.N) / inv.df[t], 10)
            qvec[t] = f * idf
    if not qvec:
        return []

    qnorm = math.sqrt(sum(x * x for x in qvec.values()))
    if qnorm == 0:
        return []

    scores = defaultdict(float)
    for t, qv in qvec.items():
        for d, post in inv.postings(t).items():
            scores[d] += qv * post.tfidf

    results: List[Tuple[int, float]] = []
    for d, dot in scores.items():
        denom = qnorm * inv.docs[d].norm
        if denom > 0:
            results.append((d, dot / denom))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:topk]