# src/mysearch/part4_core.py
"""
Part 4 core logic: query reformulation by term correlation.

Algorithm (per project handout):
1. For a query q, get a ranked set S using the base search engine.
2. Select a small top subset A from S (for example 5 docs).
3. Collect keywords from docs in A into a candidate set K.
4. For each term in K, compute a correlation score with query terms
   using tf-idf postings in the inverted index.
5. Pick a few top correlated terms and expand q with them.
6. Run the expanded query and get a new ranked set S'.
7. For evaluation, we will show S and S' in different colors in the GUI.
"""

from collections import defaultdict
from typing import Dict, List, Set, Tuple

from .part3_spider import (
    InvertedIndex,   # same index structure as Part 3
    vector_rank,     # base ranking function (tf-idf + cosine)
    WORD_RE,         # regex for tokenization
    STOPWORDS,       # stop word list
)


def _normalize_terms(text: str) -> List[str]:
    """
    Tokenize a free text string into lowercase terms with stop words removed.
    Reuses the WORD_RE and STOPWORDS config from Part 3.
    """
    raw = (m.group(0).lower() for m in WORD_RE.finditer(text))
    return [t for t in raw if t not in STOPWORDS]


def _ensure_doc_terms(inv: InvertedIndex) -> None:
    """
    Build a doc -> {term: tfidf} map once and attach it to the index.
    """
    if hasattr(inv, "doc_terms"):
        return

    doc_terms: Dict[int, Dict[str, float]] = {d: {} for d in inv.docs}
    for term, postings in inv.index.items():   # <– changed here
        for doc_id, post in postings.items():
            doc_terms[doc_id][term] = post.tfidf

    inv.doc_terms = doc_terms  # type: ignore[attr-defined]



def _term_corr(inv: InvertedIndex, t1: str, t2: str) -> float:
    """
    Correlation between two terms using tf-idf postings.

    corr(t1, t2) = sum over documents of tfidf(t1, d) * tfidf(t2, d)

    We do not build the full W^T * W matrix. Instead we walk the smaller
    postings map and probe into the other one.
    """
    p1 = inv.postings(t1)
    p2 = inv.postings(t2)
    if not p1 or not p2:
        return 0.0

    # Always iterate the smaller postings dict
    if len(p1) > len(p2):
        p1, p2 = p2, p1

    s = 0.0
    for doc_id, post1 in p1.items():
        post2 = p2.get(doc_id)
        if post2 is not None:
            s += post1.tfidf * post2.tfidf
    return s


def _pick_expansion_terms(
    inv: InvertedIndex,
    query_terms: List[str],
    candidate_terms: Set[str],
    max_added: int = 5,
) -> List[str]:
    """
    From a candidate term set K, choose up to max_added terms that are
    most correlated with the original query terms.

    For each term k in K we compute:
        score(k) = sum_q corr(q, k)
    and pick the top scoring ones.
    """
    # Avoid re-adding exact query terms
    candidate_terms = {t for t in candidate_terms if t not in query_terms}
    if not candidate_terms:
        return []

    scores: Dict[str, float] = {}
    for cand in candidate_terms:
        total = 0.0
        for q in query_terms:
            total += _term_corr(inv, q, cand)
        scores[cand] = total

    # Sort by correlation score descending
    sorted_terms = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [t for t, s in sorted_terms[:max_added] if s > 0.0]


def reformulate_and_search(
    inv: InvertedIndex,
    query: str,
    top_docs_for_feedback: int = 5,
    expansion_terms: int = 5,
    initial_topk: int = 40,
    final_topk: int = 40,
) -> Tuple[
    str,                     # expanded query string
    List[str],               # added expansion terms
    List[Tuple[int, float]], # original ranked list S
    List[Tuple[int, float]], # expanded ranked list S'
]:
    """
    Full pipeline for Part 4.

    Returns:
      expanded_query, added_terms, ranked_S, ranked_S_prime
    """
    # 1) initial ranked result S
    ranked_S = vector_rank(inv, query, topk=initial_topk)
    if not ranked_S:
        return query, [], [], []

    # 2) pick top docs A for pseudo relevance feedback
    top_docs = [doc_id for doc_id, _ in ranked_S[:top_docs_for_feedback]]

    # 3) candidate keywords from A
    _ensure_doc_terms(inv)
    doc_terms = inv.doc_terms  # type: ignore[attr-defined]

    candidate_terms: Set[str] = set()
    for d in top_docs:
        candidate_terms.update(doc_terms.get(d, {}).keys())

    # 4) choose expansion terms by correlation
    q_terms = _normalize_terms(query)
    added = _pick_expansion_terms(inv, q_terms, candidate_terms,
                                  max_added=expansion_terms)

    if not added:
        # No useful new terms: just reuse original ranking
        return query, [], ranked_S, ranked_S

    expanded_query = query.strip() + " " + " ".join(added)

    # 5) run expanded query to get S'
    ranked_S_prime = vector_rank(inv, expanded_query, topk=final_topk)

    return expanded_query, added, ranked_S, ranked_S_prime
