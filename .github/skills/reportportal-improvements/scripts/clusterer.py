"""
clusterer.py — groups similar failures within a launch using MiniLM + HDBSCAN.

Usage:
    from clusterer import build_clusters
    clusters = build_clusters(failures)   # failures = list of dicts from log_parser
"""

import numpy as np
from sentence_transformers import SentenceTransformer
import hdbscan

# Load once at module level — ~80MB, CPU inference <10ms per log
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(messages: list[str]) -> np.ndarray:
    """Encode short failure messages to 384-dim vectors."""
    return _model.encode(messages, batch_size=64, show_progress_bar=False)


def cluster(embeddings: np.ndarray, min_cluster_size: int = 2) -> np.ndarray:
    """
    HDBSCAN — no need to specify k.
    label = -1  →  noise / unclustered (shown as "Novel" in UI)
    """
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=1,
        metric="euclidean",
    )
    return clusterer.fit_predict(embeddings)


def build_clusters(failures: list[dict]) -> list[dict]:
    """
    Input:
        failures — list of dicts with keys:
            test_id, exception_type, message, root_file, root_line

    Output:
        list of cluster groups sorted by count descending:
        [
          { cluster_id, label, count, is_novel, members: [test_id, ...] },
          ...
        ]
    """
    if not failures:
        return []

    texts = [f"{f['exception_type']}: {f['message']}" for f in failures]
    embeddings = embed(texts)
    labels = cluster(embeddings)

    groups: dict[int, list] = {}
    for i, label in enumerate(labels):
        groups.setdefault(int(label), []).append(failures[i])

    result = []
    for label, members in sorted(groups.items(), key=lambda x: -len(x[1])):
        result.append({
            "cluster_id": label,
            "label": _label_for(members),
            "count": len(members),
            "is_novel": label == -1,
            "members": [m["test_id"] for m in members],
        })
    return result


def _label_for(members: list[dict]) -> str:
    types = [m["exception_type"] for m in members]
    top_type = max(set(types), key=types.count)
    root = members[0].get("root_file", "")
    return f"{top_type} — {root}" if root else top_type


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_failures = [
        {"test_id": "t1", "exception_type": "AssertionError", "message": "Expected 200, got 502", "root_file": "payment.py", "root_line": 88},
        {"test_id": "t2", "exception_type": "AssertionError", "message": "Expected 200 but received 502", "root_file": "checkout.py", "root_line": 42},
        {"test_id": "t3", "exception_type": "TimeoutError",   "message": "Session expired after 30s",    "root_file": "session.py",  "root_line": 10},
        {"test_id": "t4", "exception_type": "AssertionError", "message": "user role expected admin",      "root_file": "auth.py",     "root_line": 55},
    ]
    clusters = build_clusters(sample_failures)
    for c in clusters:
        tag = "[NOVEL]" if c["is_novel"] else ""
        print(f"Cluster {c['cluster_id']} {tag}: {c['label']} — {c['count']} tests")
        print(f"  Members: {c['members']}")
