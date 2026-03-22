"""
search_index.py — builds and queries the FAISS semantic failure index.

Usage:
    from search_index import build_index, search
    build_index(failures)
    results = search("payment service timeout", top_k=5)
"""

import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

_model      = SentenceTransformer("all-MiniLM-L6-v2")
INDEX_PATH  = Path("data/failures.faiss")
META_PATH   = Path("data/failures_meta.pkl")


def build_index(failures: list[dict]):
    """
    Build (or rebuild) the FAISS flat index from a list of failure dicts.

    failures must have: failure_id, exception_type, message, test_name, launch_id
    """
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    texts      = [f"{f['exception_type']}: {f['message']}" for f in failures]
    embeddings = _model.encode(texts, batch_size=64, normalize_embeddings=True)

    dim   = embeddings.shape[1]               # 384 for MiniLM
    index = faiss.IndexFlatIP(dim)            # inner product on normalised = cosine sim
    index.add(embeddings.astype("float32"))

    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(failures, f)

    print(f"Index built: {len(failures)} failures, dim={dim}")


def search(query: str, top_k: int = 5) -> list[dict]:
    """Returns top_k most similar historical failures with cosine score."""
    if not INDEX_PATH.exists():
        raise FileNotFoundError("Index not built yet — run build_index() first.")

    index = faiss.read_index(str(INDEX_PATH))
    with open(META_PATH, "rb") as f:
        metadata: list[dict] = pickle.load(f)

    q_emb = _model.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = index.search(q_emb, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        item = metadata[idx].copy()
        item["score"] = round(float(score), 3)
        results.append(item)
    return results


def add_failure(failure: dict):
    """Append a single new failure to the existing index (incremental update)."""
    if not INDEX_PATH.exists():
        return build_index([failure])

    index = faiss.read_index(str(INDEX_PATH))
    with open(META_PATH, "rb") as f:
        metadata = pickle.load(f)

    text  = f"{failure['exception_type']}: {failure['message']}"
    emb   = _model.encode([text], normalize_embeddings=True).astype("float32")
    index.add(emb)
    metadata.append(failure)

    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(metadata, f)


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = [
        {"failure_id": "f1", "exception_type": "AssertionError", "message": "Expected 200, got 502", "test_name": "test_payment_gateway", "launch_id": "138"},
        {"failure_id": "f2", "exception_type": "TimeoutError",   "message": "Session expired after 30s", "test_name": "test_session", "launch_id": "135"},
        {"failure_id": "f3", "exception_type": "AssertionError", "message": "Expected 200 but received 502", "test_name": "test_refund", "launch_id": "131"},
    ]
    build_index(sample)
    hits = search("payment service 502 error", top_k=3)
    for h in hits:
        print(f"  score={h['score']}  {h['test_name']}: {h['message']}")
