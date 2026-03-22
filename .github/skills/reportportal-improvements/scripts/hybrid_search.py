"""
hybrid_search.py — merges FAISS semantic results with BM25 keyword results via RRF.

Usage:
    from hybrid_search import hybrid_search
    results = hybrid_search(query="payment timeout", corpus=all_failures, top_k=10)
"""

from rank_bm25 import BM25Okapi
from search_index import search as faiss_search


def tokenise(text: str) -> list[str]:
    return text.lower().split()


def hybrid_search(query: str, corpus: list[dict], top_k: int = 10) -> list[dict]:
    """
    1. Top-20 from FAISS  (semantic — handles paraphrases)
    2. Top-20 from BM25   (keyword — handles exact class/error-code matches)
    3. Merge with RRF     (no weight tuning needed)

    corpus — list of failure dicts, same shape as build_index() input
    """
    semantic = faiss_search(query, top_k=20)
    sem_rank = {r["failure_id"]: rank for rank, r in enumerate(semantic)}

    texts     = [f"{c['exception_type']}: {c['message']}" for c in corpus]
    bm25      = BM25Okapi([tokenise(t) for t in texts])
    bm25_raw  = bm25.get_scores(tokenise(query))
    bm25_order = sorted(range(len(corpus)), key=lambda i: -bm25_raw[i])
    bm25_rank  = {corpus[i]["failure_id"]: rank for rank, i in enumerate(bm25_order[:20])}

    # Reciprocal Rank Fusion — k=60 is the standard constant
    k       = 60
    all_ids = set(sem_rank) | set(bm25_rank)
    rrf     = {
        fid: (1 / (k + sem_rank.get(fid, 1000))) + (1 / (k + bm25_rank.get(fid, 1000)))
        for fid in all_ids
    }

    top_ids = sorted(rrf, key=lambda x: -rrf[x])[:top_k]

    # Build lookup from both result sets
    lookup: dict[str, dict] = {r["failure_id"]: r for r in semantic}
    lookup.update({c["failure_id"]: c for c in corpus if c["failure_id"] in top_ids})

    return [
        {**lookup[fid], "score": round(rrf[fid], 4)}
        for fid in top_ids if fid in lookup
    ]


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Requires search_index to have been built first
    corpus = [
        {"failure_id": "f1", "exception_type": "AssertionError", "message": "Expected 200, got 502", "test_name": "test_payment_gateway", "launch_id": "138"},
        {"failure_id": "f2", "exception_type": "TimeoutError",   "message": "Session expired after 30s", "test_name": "test_session", "launch_id": "135"},
        {"failure_id": "f3", "exception_type": "AssertionError", "message": "Expected 200 but received 502", "test_name": "test_refund", "launch_id": "131"},
    ]

    from search_index import build_index
    build_index(corpus)

    results = hybrid_search("payment 502 error", corpus=corpus, top_k=3)
    for r in results:
        print(f"  rrf={r['score']}  {r['test_name']}: {r['message']}")
