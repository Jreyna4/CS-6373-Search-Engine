"""
Part 3 – Spider + Indexer

This spider extends the Part 2 InvertedIndex to crawl through all HTML/HTM
documents inside rhf.zip. It indexes each document’s content for later search.
"""

from pathlib import Path
import zipfile
from io import TextIOWrapper
from collections import defaultdict
import re
import math

from .part2_core import InvertedIndex, _resolve_zip, DocInfo, Posting, tokenize, STOPWORDS


class Spider(InvertedIndex):
    """Spider that reads and indexes all .html/.htm files inside rhf.zip."""

    def __init__(self, zip_filename: str = "rhf.zip"):
        super().__init__()
        self.zip_path = _resolve_zip(zip_filename)
        self.total_files = 0
        self.html_files = []

    def crawl_zip(self, zip_path: str | None = None):
        """Traverse all HTML/HTM files in the zip and index them."""
        path_to_use = zip_path or self.zip_path
        print(f"[*] Crawling {path_to_use} ...")

        try:
            with zipfile.ZipFile(path_to_use, "r") as zf:
                # Collect HTML/HTM files
                self.html_files = [f for f in zf.namelist() if f.lower().endswith((".html", ".htm"))]
                self.total_files = len(self.html_files)

                for file_name in self.html_files:
                    try:
                        with zf.open(file_name, "r") as file:
                            text = TextIOWrapper(file, encoding="utf-8", errors="ignore").read()
                        # --- Index the document manually ---
                        words = [w for w in tokenize(text) if w not in STOPWORDS]
                        if not words:
                            continue

                        doc_id = self.N
                        self.docs[doc_id] = DocInfo(path=f"./{file_name}", length=len(words))

                        # Build postings
                        pos_map = defaultdict(list)
                        for i, w in enumerate(words):
                            pos_map[w].append(i)

                        for w, positions in pos_map.items():
                            self.inv.setdefault(w, {})[doc_id] = Posting(freq=len(positions), positions=positions)

                        self.N += 1

                    except Exception as e:
                        print(f"  [!] Failed to index {file_name}: {e}")

        except FileNotFoundError:
            print(f"[!] ZIP file not found: {path_to_use}")
        except zipfile.BadZipFile:
            print(f"[!] Invalid ZIP file: {path_to_use}")

        # Compute document frequencies
        for term, postings in self.inv.items():
            self.df[term] = len(postings)

        # Compute tf-idf weights and document norms
        for term, postings in self.inv.items():
            idf = math.log((self.N) / self.df[term], 10) if self.df[term] else 0.0
            for d, post in postings.items():
                post.tfidf = post.freq * idf
                self.docs[d].norm += post.tfidf ** 2

        for doc in self.docs.values():
            doc.norm = math.sqrt(doc.norm)

        print(f"\n✅ Indexed {self.N} HTML files.")
        print(f"Total unique terms: {len(self.inv)}")


def build_spider_index(zip_filename: str = "rhf.zip") -> Spider:
    """Convenience wrapper to create and crawl the corpus."""
    spider = Spider(zip_filename)
    spider.crawl_zip()
    return spider
