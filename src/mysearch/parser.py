"""CSCI 6373 — Part 1 HTML parser utilities (PyInstaller-ready)

Purpose
-------
Provide two core functions:
- `build_index(zip_name="Jan.zip")`: read every `.html` in the provided zip and
  extract **alphabetic-only** words, lowercased, as per the assignment.
- `search_files(index, key)`: return the list of files containing the key.
Also provides `build_index_at(path)` for GUIs that let a user pick a zip.

How it works
------------
1) **Locate `Jan.zip` automatically** (robust to different run modes):
   - Walks up parent directories from BOTH the current working directory and
     this file's directory (covers running from repo root, `src/`, etc.).
   - When packaged with **PyInstaller**:
       * Checks the one-file extraction dir `sys._MEIPASS`.
       * Checks the folder containing the frozen executable.
2) **Extract visible text**:
   - If `beautifulsoup4` is available, strip `script/style/noscript` tags and
     use `get_text()`.
   - Otherwise fall back to a simple regex that removes HTML tags.
3) **Tokenize** with a regex that keeps only A–Z letters and lowercases.
4) Build an in-memory mapping: `filename -> set(tokens)`.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Set, Iterable, Union

try:
    from bs4 import BeautifulSoup  # optional but recommended
except Exception:
    BeautifulSoup = None  # fallback to regex if not installed

WORD_RE = re.compile(r"[A-Za-z]+")

def _text_from_html(html: str) -> str:
    """Extract visible text from HTML. Prefer BeautifulSoup; fallback to regex."""
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        return soup.get_text(separator=" ")
    # very naive fallback: strip tags and keep text-ish content
    no_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", no_tags)

def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]

# ---------- Jan.zip locator ----------
def _candidates_for(zip_name: str) -> Iterable[Path]:
    """Yield candidate paths to search for the zip."""
    # 1) CWD and its first few parents
    cwd = Path.cwd().resolve()
    for p in [cwd, *list(cwd.parents)[:6]]:
        yield p / zip_name
    # 2) This file's directory and its first few parents
    here = Path(__file__).resolve()
    for p in [here.parent, *list(here.parents)[:6]]:
        yield p / zip_name
    # 3) PyInstaller one-file extraction dir (_MEIPASS) if present
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            yield Path(sys._MEIPASS) / zip_name  # type: ignore[attr-defined]
        except Exception:
            pass
    # 4) Folder containing the frozen executable (one-folder builds)
    if getattr(sys, "frozen", False):
        try:
            exe_dir = Path(sys.executable).resolve().parent
            yield exe_dir / zip_name
        except Exception:
            pass

def _find_zip(zip_name: str) -> Path:
    """Return the first existing path to zip_name from our candidates."""
    seen: Set[Path] = set()
    for cand in _candidates_for(zip_name):
        try:
            c = cand.resolve()
        except Exception:
            c = cand
        if c in seen:
            continue
        seen.add(c)
        if c.exists():
            return c
    raise FileNotFoundError(f"Could not locate {zip_name} by searching CWD, package dirs, and frozen paths.")

# ---------- Public API ----------
def build_index(zip_name: str = "Jan.zip") -> Dict[str, Set[str]]:
    """
    Build an index mapping filename -> set of lowercase alphabetic terms,
    searching for a zip file named `zip_name`.
    """
    zip_path = _find_zip(zip_name)
    return build_index_at(zip_path)

def build_index_at(zip_path: Union[str, Path]) -> Dict[str, Set[str]]:
    """
    Build an index using an explicit path to a .zip (used by the GUI's 'Open' button).
    """
    zp = Path(zip_path)
    if not zp.exists():
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    index: Dict[str, Set[str]] = {}
    with zipfile.ZipFile(zp, "r") as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".html"):
                continue
            with zf.open(member, "r") as fh:
                html = fh.read().decode(errors="ignore")
            text = _text_from_html(html)
            terms = set(_tokenize(text))
            index[member] = terms
    return index

def search_files(index: Dict[str, Set[str]], key: str) -> List[str]:
    key = key.lower().strip()
    if not key:
        return []
    return sorted([fname for fname, terms in index.items() if key in terms])

if __name__ == "__main__":
    idx = build_index()
    while True:
        print("enter a search key=> ", end="")
        key = input().strip()
        if key == "":
            print("Bye")
            break
        matches = search_files(idx, key)
        if matches:
            for m in matches:
                print(f"found a match:  ./Jan/{Path(m).name}")
        else:
            print("no match")