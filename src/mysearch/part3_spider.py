# src/mysearch/part3_spider.py
"""
Part 3 — Simple ZIP Spider + Inverted Index + Query Engine

Goal
- Crawl a local ZIP corpus (rhf.zip) starting at rhf/index.html
- Parse HTML to visible text
- Build a positional inverted index with tf, df, tf-idf, and document vector norms 
- Support:
    1) Boolean OR / AND / BUT (strict)
    2) Phrase search with double quotes: "information retrieval evaluation"
    3) Free text ranking using cosine similarity

Design choices
- Keep the code self-contained so Part 3 does not depend on Part 2 (at the cost of some duplication)

"""

from __future__ import annotations

import pickle
import pathlib

import os
import re
import math
import zipfile
import tempfile
import webbrowser
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from bs4 import BeautifulSoup, Comment


# -----------------------------
# Basic tokenization and config
# -----------------------------

WORD_RE = re.compile(r"[A-Za-z']+")  # allow simple apostrophes like don't

STOPWORDS: Set[str] = {
    "a","an","the","and","or","but","of","in","on","to","for","from","by","with",
    "about","as","at","into","through","during","before","after","above","below",
    "under","over","again","further","then","once","here","there","when","where",
    "why","how","all","any","both","each","few","more","most","other","some","such",
    "no","nor","not","only","own","same","so","than","too","very","can","will","just",
    "is","are","was","were","be","been","being","it","its","that","this","these","those",
    "he","she","they","them","we","you","i","me","my","our","your","their","his","her",
    "who","whom","which","what"
}

def _tokens_from_text(text: str) -> List[str]:
    """Lowercase tokens, filter stopwords. Keep simple alphabetic words."""
    toks = (m.group(0).lower() for m in WORD_RE.finditer(text))
    return [t for t in toks if t.strip("'") and t not in STOPWORDS]


# -----------------------------
# Inverted index data model
# -----------------------------

@dataclass
class Posting:
    tf: int = 0
    positions: List[int] = field(default_factory=list)
    tfidf: float = 0.0

@dataclass
class DocInfo:
    path: str
    title: str = ""
    text: str = ""     # full visible text for snippets
    length: int = 0
    norm: float = 0.0  # vector length for cosine


class InvertedIndex:
    def __init__(self):
        # term -> {doc_id -> Posting}
        self.index: Dict[str, Dict[int, Posting]] = {}
        # doc_id -> DocInfo
        self.docs: Dict[int, DocInfo] = {}
        # term -> document frequency
        self.df: Dict[str, int] = {}
        # number of documents
        self.N: int = 0

    def postings(self, term: str) -> Dict[int, Posting]:
        return self.index.get(term, {})


# -----------------------------
# HTML parsing
# -----------------------------

def _make_soup(raw: bytes):
    """
    Use lxml parser if available (faster); fall back to html.parser.
    """
    try:
        return BeautifulSoup(raw, "lxml")
    except Exception:
        return BeautifulSoup(raw, "html.parser")

def _clean_html(raw: bytes) -> Tuple[str, str, List[Tuple[str, str]]]:
    """
    Return (title, visible_text, links-as-(href,anchor_text)).
    - Removes <script>, <style>, and HTML comments.
    """
    soup = _make_soup(raw)
    for s in soup.find_all(["style", "script"]):
        s.extract()
    for c in soup(text=lambda it: isinstance(it, Comment)):
        c.extract()

    title = soup.title.get_text(strip=True) if soup.title else ""
    text = soup.get_text(separator=" ")
    links: List[Tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        anchor = a.get_text(" ", strip=True)
        links.append((href, anchor))
    return title, text, links


# -----------------------------
# Spider over a ZIP archive
# -----------------------------

_HTML = re.compile(r"\.(html?|HTML?)$")

def _is_html(name: str) -> bool:
    return bool(_HTML.search(name))

def _norm_zip_path(p: str) -> str:
    """Normalize to forward slashes so joins are consistent inside ZIP."""
    return p.replace("\\", "/")

def _resolve_rel(base: str, href: str) -> str:
    """
    Resolve a relative link inside the ZIP.
    - Ignore external http(s)
    - Drop URL fragments (#...)
    - Return empty string if it points outside
    """
    href = href.split("#", 1)[0]
    if not href or href.startswith("http://") or href.startswith("https://"):
        return ""
    if href.startswith("/"):
        href = href[1:]
    base_dir = "/".join(base.split("/")[:-1])
    joined = _norm_zip_path(os.path.normpath(os.path.join(base_dir, href)))
    return joined

def spider_zip(zip_path: str, start: str = "rhf/index.html") -> Tuple[Dict[str, Tuple[str, str]], Dict[str, List[str]]]:
    """
    Breadth-first crawl inside the ZIP starting at start.
    Returns:
      pages:   path -> visible text (string)
      anchors: target_path -> list of incoming anchor texts
    Only reachable HTML files are kept.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(_norm_zip_path(n) for n in zf.namelist())

        # Handle rhf vs rfh naming quirk
        if start not in names:
            alt = "rfh/index.html"
            if alt in names:
                start = alt
            else:
                raise FileNotFoundError(f"Cannot find start page '{start}' in {zip_path}")

        q = deque([start])
        seen: Set[str] = set()
        pages: Dict[str, Tuple[str, str]] = {}
        incoming: Dict[str, List[str]] = defaultdict(list)

        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            if not _is_html(cur):
                continue

            raw = zf.read(cur)
            title, text, links = _clean_html(raw)   # FIX: correct unpack
            pages[cur] = (title, text)              # FIX: store (title, text)

            for href, anch in links:
                tgt = _resolve_rel(cur, href)
                if not tgt:
                    continue
                if tgt in names and _is_html(tgt) and tgt not in seen:
                    q.append(tgt)
                if tgt in names and _is_html(tgt) and anch:
                    incoming[tgt].append(anch)

        for name in names:
            if _is_html(name) and name not in pages:
                raw = zf.read(name)
                title, text, _ = _clean_html(raw)
                pages[name] = (title, text)

        return pages, incoming

def make_snippet(text: str, terms: Set[str], win: int = 80) -> str:
    """
    Return a short '...window...' around the earliest occurrence of any term.
    """
    if not text or not terms:
        return ""
    tlow = text.lower()
    hits = [tlow.find(t) for t in terms if t]
    hits = [h for h in hits if h >= 0]
    if not hits:
        return ""
    i = min(hits)
    start = max(0, i - win // 2)
    end = min(len(text), start + win)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


# -----------------------------
# Build the inverted index
# -----------------------------

def _zip_signature(zip_path: str) -> tuple[int, float]:
    """
    Return (size, mtime) so we can invalidate the cache when the ZIP changes.
    """
    p = pathlib.Path(zip_path)
    stat = p.stat()
    return (stat.st_size, stat.st_mtime)

def build_index_from_spider(zip_path: str,
                            start: str = "rhf/index.html",
                            use_cache: bool = True,
                            cache_dir: str = ".cache") -> tuple[InvertedIndex, bool]:
    """
    Crawl all HTML pages in the ZIP, tokenize, add incoming anchor tokens,
    and compute tf-idf and norms.

    If use_cache=True (default), load/save a pickle of the built index keyed
    by ZIP size+mtime to skip work on repeat runs.

    Returns: (inv, from_cache)
    """
    sig = _zip_signature(zip_path)
    cache_root = pathlib.Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_file = cache_root / f"part3_index_{pathlib.Path(zip_path).name}_{sig[0]}_{int(sig[1])}.pkl"

    if use_cache and cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                inv = pickle.load(f)
            return inv, True
        except Exception:
            # Corrupt cache; ignore and rebuild
            pass

    pages, incoming = spider_zip(zip_path, start)
    inv = InvertedIndex()

    # Stable numbering of docs
    ordered = sorted(pages.keys())
    path_to_id = {p: i for i, p in enumerate(ordered)}

    for path, doc_id in path_to_id.items():
        title, body_text = pages[path]

        # Tokens from body
        body = _tokens_from_text(body_text)

        # Tokens from incoming anchors (credited to target)
        extra: List[str] = []
        for a in incoming.get(path, []):
            extra.extend(_tokens_from_text(a))
        tokens = body + extra

        inv.docs[doc_id] = DocInfo(
            path=f"./{path}",
            title=title,
            text=body_text,
            length=len(tokens),
        )

        # Collect positions per term for this document
        pos: Dict[str, List[int]] = defaultdict(list)
        for i, t in enumerate(tokens):
            pos[t].append(i)

        # Fill postings
        for term, plist in pos.items():
            inv.index.setdefault(term, {})[doc_id] = Posting(tf=len(plist), positions=plist)

    # Compute df, tf-idf, and vector norms
    inv.N = len(inv.docs)
    inv.df = {t: len(p) for t, p in inv.index.items()}

    for term, postings in inv.index.items():
        idf = math.log((inv.N) / inv.df[term], 10) if inv.df[term] else 0.0
        for d, post in postings.items():
            tfw = 1.0 + (math.log(post.tf, 10) if post.tf > 0 else 0.0)
            w = tfw * idf
            post.tfidf = w
            inv.docs[d].norm += w * w

    for d in inv.docs:
        inv.docs[d].norm = math.sqrt(inv.docs[d].norm)

    if use_cache:
        try:
            with cache_file.open("wb") as f:
                pickle.dump(inv, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass  # caching is a best-effort optimization

    return inv, False


# -----------------------------
# Query processing
# -----------------------------

def _docset(inv: InvertedIndex, term: str) -> Set[int]:
    return set(inv.postings(term).keys())

def boolean_or(inv: InvertedIndex, terms: List[str]) -> Set[int]:
    """Strict OR: union of posting lists."""
    out: Set[int] = set()
    for t in terms:
        out |= _docset(inv, t)
    return out

def boolean_and(inv: InvertedIndex, terms: List[str]) -> Set[int]:
    """Strict AND: intersection, starting from the rarest term for speed."""
    terms = [t for t in terms if t]
    if not terms:
        return set()
    terms_sorted = sorted(terms, key=lambda x: len(inv.postings(x)))
    current = set(inv.postings(terms_sorted[0]).keys())
    for t in terms_sorted[1:]:
        current &= set(inv.postings(t).keys())
        if not current:
            break
    return current

def boolean_but(inv: InvertedIndex, left: List[str], right: List[str]) -> Set[int]:
    """Left AND minus Right OR."""
    return boolean_and(inv, left) - boolean_or(inv, right)

def phrase_search(inv: InvertedIndex, phrase: str) -> Set[int]:
    """
    Exact consecutive phrase over the *indexed* terms (stopwords removed at index time).
    Steps:
      1) Intersect docs of the phrase terms that are actually in the index
      2) Verify adjacency using positions
    """
    words = [w for w in (m.group(0).lower() for m in WORD_RE.finditer(phrase)) if w not in STOPWORDS]
    if not words:
        return set()

    # Only keep terms present in the index; if none, no candidates
    words = [w for w in words if w in inv.index]
    if not words:
        return set()

    cand = boolean_and(inv, words)
    out: Set[int] = set()
    for d in cand:
        # All words are guaranteed to be in index
        pos_lists = [inv.postings(w)[d].positions for w in words if d in inv.postings(w)]
        if len(pos_lists) != len(words):
            continue
        next_sets = [set(lst) for lst in pos_lists[1:]]
        for p0 in pos_lists[0]:
            if all((p0 + i + 1) in next_sets[i] for i in range(len(next_sets))):
                out.add(d)
                break
    return out


def vector_rank(inv: InvertedIndex, query: str, topk: int = 30) -> List[Tuple[int, float]]:
    """
    Cosine similarity between query and doc vectors using tf-idf weights.
    Terms not in the index are ignored.
    """
    q_terms = [w for w in (m.group(0).lower() for m in WORD_RE.finditer(query)) if w not in STOPWORDS]
    if not q_terms:
        return []

    # Query term frequencies
    q_tf: Dict[str, int] = defaultdict(int)
    for t in q_terms:
        if t in inv.df:
            q_tf[t] += 1
    if not q_tf:
        return []

    # Query weights and normalization
    q_w: Dict[str, float] = {}
    for t, f in q_tf.items():
        idf = math.log((inv.N) / inv.df[t], 10) if inv.df[t] else 0.0
        q_w[t] = (1.0 + math.log(f, 10)) * idf
    q_norm = math.sqrt(sum(w * w for w in q_w.values())) or 1.0

    # Accumulate dot product and divide by doc norm
    scores: Dict[int, float] = defaultdict(float)
    for t, qw in q_w.items():
        for d, post in inv.postings(t).items():
            denom = inv.docs[d].norm or 1.0
            scores[d] += (post.tfidf / denom) * (qw / q_norm)

    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:topk]


# -----------------------------
# Helpers to open results
# -----------------------------

def extract_zip_to_temp(zip_path: str) -> str:
    """Extract the ZIP to a temp folder so we can open files locally."""
    tmpdir = tempfile.mkdtemp(prefix="rfh_")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmpdir)
    return tmpdir

def open_local_in_browser(temp_root: str, rel_path: str) -> None:
    """Open a crawled file in the default browser."""
    import pathlib
    p = pathlib.Path(temp_root) / rel_path
    webbrowser.open_new_tab(p.resolve().as_uri())
