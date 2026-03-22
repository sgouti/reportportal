# ML Analyser Stack — Model Choices & Rationale

## Why lightweight?

Automation failure logs are short and structured:
- Exception class name (e.g. `AssertionError`)
- One-line message (e.g. `Expected 200, got 502`)
- A stack trace (usually 5–20 lines, first non-framework frame is the signal)

This is not a long-document retrieval problem. Heavy models (GPT-4, BERT-large)
are overkill and add cost/latency. The models below handle this input size optimally.

---

## Models

### all-MiniLM-L6-v2
- **Size:** ~80 MB
- **Inference:** <10ms per log on CPU (no GPU needed)
- **Dimensions:** 384
- **Why:** Trained on short text pairs (sentence similarity). Handles
  "NPE at payment.py:88" and "NullPointer thrown in checkout service" as
  semantically close — which they are. Pre-trained, no fine-tuning required.
- **Install:** `pip install sentence-transformers`
  (downloads model on first run)

### FAISS IndexFlatIP
- **Size:** ~5 MB library + index file
- **Why flat index:** For <1M failure vectors, flat inner product is fastest
  and most accurate. No quantisation loss. Cosine similarity via normalised vectors.
- **Rebuild time:** 100k failures ≈ 8s on 2-core CPU
- **Install:** `pip install faiss-cpu`

### rank-bm25
- **Size:** ~1 MB
- **Why:** Exact keyword match on error class names, file paths, test IDs.
  Semantic search alone can miss exact matches on structured tokens.
  BM25 + FAISS merged via RRF gives best of both.
- **Install:** `pip install rank-bm25`

### HDBSCAN
- **Size:** ~3 MB
- **Why:** No need to specify k (number of clusters). Handles noise as
  label=-1 (shown as "unclustered / novel" in the UI). Works well on
  dense embedding spaces. Min cluster size = 2 catches even small groups.
- **Install:** `pip install hdbscan`

---

## Install all at once

```bash
pip install sentence-transformers faiss-cpu hdbscan rank-bm25
```

No GPU. No cloud API. No per-query cost.

---

## Index update strategy

| Event | Action |
|---|---|
| Launch completes | Append new failure embeddings to FAISS index |
| Nightly cron | Full index rebuild (keeps index consistent with DB corrections) |
| First run | Full build from all historical failures |

---

## RRF merging (Phase 4)

Reciprocal Rank Fusion combines FAISS semantic ranks and BM25 keyword ranks
without needing to tune weights:

```
rrf_score(id) = 1/(k + semantic_rank) + 1/(k + bm25_rank)
```

k=60 is the standard constant. Higher score = better match.
Final results sorted by rrf_score descending.
