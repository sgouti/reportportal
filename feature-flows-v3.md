# ReportPortal — ML Feature Flows v3

> Deployment target: Local machine / CPU-bound environment
> Architecture: Two separate analyzer instances (P1 fast + P2 deep)
> Incorporates: CPU-optimized models, corrected statistical gates,
> drift-based retraining, stack trace pre-processing, FlashRank reranker

---

## Deployment Context

Everything in this document assumes a **CPU-only local machine**.
No GPU. No cloud inference. All models run via ONNX Runtime CPU provider.
Model choices, batch sizes, timeouts, and gates are set accordingly.

---

## Pre-Processing — Stack Trace Truncation (All Tiers)

Applied to every failed test item **before** any embedding or retrieval.
This runs first — no model sees a raw stack trace.

```
Raw failed test item log received
          │
          ▼
Extract only:
  Line 1: Exception type + message
  Lines 2-4: Top 3 stack frames
  Discard: remaining frames, timestamps, thread IDs

Example input (raw):
  java.lang.NullPointerException: Cannot invoke method get()
    at com.rp.PaymentService.process(PaymentService.java:142)
    at com.rp.OrderController.submit(OrderController.java:88)
    at com.rp.BaseHandler.handle(BaseHandler.java:34)
    at sun.reflect.NativeMethodAccessorImpl... (discarded)
    at java.lang.Thread.run(Thread.java:748)  (discarded)
    ... 47 more lines                         (discarded)

Example output (truncated):
  java.lang.NullPointerException: Cannot invoke method get()
  PaymentService.process:142
  OrderController.submit:88
  BaseHandler.handle:34
```

### Why This Matters
- Embedding a 10,000 char stack trace wastes CPU cycles
- Remaining frames add noise — exception type + top 3 frames
  carry ~90% of semantic meaning
- Reduces embedding input from ~2,000 tokens to ~50 tokens
- Cuts embedding inference time by ~60% on CPU

---

## Architecture Overview

```
Failed test item arrives
          │
          ▼
[PRE-PROCESSOR]
Extract: exception header + top 3 frames
          │
          ▼
┌──────────────────────────────────────┐
│  FAST ANALYZER — Priority 1          │
│  BM25 + scikit-learn                 │
│  ANALYZER_PRIORITY=1                 │
│  AA_ENABLE_ASYNC_PIPELINE=true       │
│  ANALYZER_SUGGEST=false              │
│  ANALYZER_CLUSTER=false              │
│  Rerank: FlashRank depth 5 or off    │
│  Timeout: 2s                         │
└──────────────────────────────────────┘
          │
    Confidence ≥ 70%?
    ┌─────┴──────┐
   YES           NO
    │             │
    ▼             ▼
Auto-assign    DEEP ANALYZER — Priority 2
source:        BGE-Small-EN-v1.5 ONNX INT8
fast-AA        + FlashRank TinyBERT
               + LightGBM (OpenMP)
               ANALYZER_PRIORITY=2
               ANALYZER_SUGGEST=true
               ANALYZER_CLUSTER=true (≥10 items)
               Timeout: 10s
               CPU load-shed: bypass reranker if CPU > 90%
                    │
              Confidence ≥ 55%?
              ┌─────┴──────┐
             YES            NO
              │              │
              ▼              ▼
         Auto-assign    Needs Expert Review
         source:        top 3 suggestions shown
         deep-AA        triage aging starts
```

---

## 1. Fast Analyzer — Priority 1

### Purpose
Immediate defect assignment for known and recurring failures.
Handles ~65–70% of all failures within 2 seconds on CPU.

### Service Config
```
ANALYZER_PRIORITY=1
AA_ENABLE_ASYNC_PIPELINE=true
ANALYZER_SUGGEST=false
ANALYZER_CLUSTER=false
AA_PIPELINE_TIMEOUT_SECONDS=2
```

### Reranking Strategy — Trim First, Disable Second
```
Normal load:    FlashRank depth 5   → fast enough (~30ms)
High load:      FlashRank depth 3   → trim first
CPU > 90%:      disable reranking   → BM25 scores only
```

FlashRank (ms-marco-TinyBERT-L-2-v2) is used here instead
of bge-reranker-v2-m3. TinyBERT is ONNX-native, runs in
<50ms on CPU versus 300–800ms for a cross-encoder reranker.

### Classifier Note
Tier 1 uses scikit-learn. If replacing the classifier,
use `HistGradientBoostingClassifier` — it multi-threads
across all local CPU cores via OpenMP natively.

### What It Does
- Truncated error string → BM25 retrieval → classifier
- Confidence ≥ 70% → auto-assign, tagged `fast-AA`
- Confidence < 70% → hand off to deep analyzer

### What Engineer Sees
```
✓ Auto-classified   Product Bug · Timing Issue    94%
  source: fast-AA   matched: Sprint 41 launch
```

---

## 2. Deep Analyzer — Priority 2

### Purpose
Semantic analysis of items fast analyzer could not classify.
Runs only on unresolved items — never on the full failure set.

### Service Config
```
ANALYZER_PRIORITY=2
AA_ENABLE_ASYNC_PIPELINE=true
ANALYZER_SUGGEST=true
ANALYZER_CLUSTER=true
AA_PIPELINE_TIMEOUT_SECONDS=10
```

### CPU Load-Shedding (Not Just Timeout)
```
CPU utilisation < 70%:  full pipeline (embed → rerank → classify)
CPU utilisation 70-90%: reduce rerank depth to 3
CPU utilisation > 90%:  bypass reranker entirely
                        rely on bi-encoder scores only
```
Load-shed based on CPU queue length, not just wall-clock timeout.
Timeout is the last resort — CPU gate fires first.

### Embedding Model — BGE-Small-EN-v1.5

Replaces BGE-M3 for local CPU deployment.

| Model | Params | RAM | CPU latency per item |
|---|---|---|---|
| BGE-M3 (original plan) | 567M | ~2.2GB | ~800ms–2s |
| BGE-Small-EN-v1.5 (correct) | 33M | ~130MB | ~20–40ms |

BGE-Small-EN-v1.5 exported to ONNX INT8.
INT8 chosen over INT4 for this domain — code/log text
requires more numerical precision than INT4 provides.
Less than 1% accuracy drop versus FP32 at INT8.

### Vector Search — FAISS CPU-only
Standard NumPy cosine similarity is 10–50x slower than
FAISS on modern CPUs. FAISS uses AVX2/AVX-512 SIMD
instructions. Integrated as OpenSearch plugin to avoid
maintaining a separate vector index outside OpenSearch.

### Reranker — FlashRank TinyBERT
```
BGE-Small bi-encoder retrieval → top 30 candidates
          │
FlashRank (ms-marco-TinyBERT-L-2-v2)
ONNX-native, CPU latency <50ms
          │
Top 10 reranked candidates
          │
LightGBM (OpenMP, all cores) → defect type probability
```

### What It Does
- Truncated error → BGE-Small ONNX INT8 embedding
- FAISS CPU search → top 30 candidates
- FlashRank reranker → top 10 (bypassed if CPU > 90%)
- LightGBM → probability per defect type
- Confidence ≥ 55% → auto-assign, tagged `deep-AA`
- Confidence < 55% → `Needs Expert Review` + top 3 suggestions

### What Engineer Sees
```
✓ Auto-classified   Automation Bug · Selector broken  71%
  source: deep-AA   matched: Sprint 38 launch

⚠ Needs Expert Review
  source: unresolved
  1. System Issue · DB Timeout    52%  [semantic]  [Apply]
  2. Automation Bug · Timing      41%  [keyword]   [Apply]
  3. Product Bug · API Changed    28%  [hybrid]    [Apply]
```

---

## 3. Analysis-Stage Metadata (Mandatory)

Every auto-classified item carries a visible source tag.
This is not optional — engineers must know which tier decided.

| Tag | Meaning | Trust Level |
|---|---|---|
| `fast-AA` | Priority-1 BM25 + scikit-learn | High for known errors |
| `deep-AA` | Priority-2 BGE-Small + LightGBM | Medium — semantic match |
| `unresolved` | Neither tier classified | Manual triage required |

Confidence score display per tier:

| Confidence | Visual | Action |
|---|---|---|
| ≥ 90% | Green | Trust it |
| 70–89% | Default | Confident |
| 50–69% | Amber + dot | Review recommended |
| < 50% | Never auto-classified | Suggestions shown |

Platt Scaling applied to raw LightGBM scores so displayed
confidence reflects true calibrated probabilities, not
raw model output which is poorly calibrated by default.

---

## 4. Flakiness Detection

### How It Works

Flakiness is a statistics problem, not an inference problem.
service-api computes history statistics. PyOD scores result.
No analyzer service involved. No embedding used.

```
Launch completes
          │
          ▼
service-api queries item history
from existing launch data
          │
          ▼
Gate 1: leaf test item only
        (not suite or folder row —
         fix at itemInfo.jsx:207,
         itemInfo.jsx:244,
         flakinessBadge.jsx:85)
          │
Gate 2: history count check
    ┌────┴─────────────────────┐
  < 10 runs               ≥ 10 runs
    │                         │
    ▼                         ▼
Deterministic logic      PyOD IsolationForest
Has at least 1 pass      on 5-feature vector
AND 1 fail in history?
    │
  YES → show UNSTABLE badge
  NO  → no badge
```

### Why ≥ 10 Runs (Not 3)
IsolationForest requires minimum 10–15 samples to produce
statistically valid anomaly scores. At 3 runs, the algorithm
produces noise — high false positive rate, low reliability.
3-run gate was a statistical error in v1 and v2.

Below 10 runs: deterministic rule replaces ML scoring.
If the test has ever both passed and failed → UNSTABLE.
Simple, honest, no false precision.

### 5-Feature Vector (for ≥ 10 runs)

```
1. pass_rate:        fraction of passed runs (0–1)
2. alternation_rate: how often status flips between runs (0–1)
3. streak_length:    avg consecutive same-status runs
4. recent_trend:     last 5 runs pass rate vs overall rate
5. std_dev:          standard deviation of binary outcomes
```

### Score Thresholds (PyOD output)

| Runs | Method | Score | Label | Action |
|---|---|---|---|---|
| < 10 | Deterministic | pass+fail present | UNSTABLE | Amber badge |
| < 10 | Deterministic | only pass or only fail | No badge | Nothing shown |
| ≥ 10 | IsolationForest | 0–20 | STABLE | No badge |
| ≥ 10 | IsolationForest | 21–50 | UNSTABLE | Amber badge |
| ≥ 10 | IsolationForest | 51–75 | FLAKY | Orange badge + alert |
| ≥ 10 | IsolationForest | 76–100 | CRITICAL | Red + quarantine + alert |

### Quarantine
- Quarantined items excluded from pass rate
- Both rates shown: `Pass rate: 91% (94% excl. 6 quarantined)`
- Engineer releases manually after fix
- Releasing resets history to zero

---

## 5. Root Cause Clustering

### How It Works

Deep analyzer (P2) only. ANALYZER_CLUSTER=false on P1.
Minimum 10 unresolved items (not 5 — prevents coarse clusters).
BM25 pre-filter applied before embedding to reduce vector space.

```
Deep analyzer has N unresolved items
          │
    N ≥ 10?
    ┌─────┴─────┐
   YES          NO
    │            └── show items individually
    ▼
BM25 pre-filter
Group obviously related items first
Reduce embedding workload
    │
    ▼
BGE-Small-EN-v1.5 ONNX INT8
encode error strings in batches of 32
(strict batch size — prevents OOM on local RAM)
    │
    ▼
HDBSCAN clustering on vector space
    │
    ▼
Cluster 1: 31 items  "DB connection refused"
Cluster 2: 12 items  "Auth token expired"
Cluster 3:  4 items  "UI selector not found"
    │
    ▼
Engineer triages one cluster
= all items classified at once
= one JIRA ticket covers all
```

### Key Constraints
- Batch size: strictly 32 embeddings at a time (OOM prevention)
- BM25 pre-filter before embedding (reduces vector space)
- Minimum 10 items (not 5) for reliable cluster quality
- BGE-Small used instead of BGE-M3 (4x less RAM)

---

## 6. Ranked ML Suggestions

Deep analyzer (P2) only. ANALYZER_SUGGEST=false on P1.
Only fires when confidence < 55% after full deep analysis.

```
Item unresolved (confidence < 55%)
          │
          ▼
BGE-Small hybrid retrieval → top 30
FlashRank TinyBERT → reranked top 10
LightGBM → probability per defect type
          │
          ▼
Top 3 shown:
1. Automation Bug · Timing    87%  [semantic]  [Apply]
2. Product Bug · API Change   61%  [keyword]   [Apply]
3. System Issue · DB Timeout  45%  [hybrid]    [Apply]
```

Match source tags:
- `semantic` — BGE-Small dense match (meaning-based)
- `keyword` — BM25 match (word-based)
- `hybrid` — both signals agreed

---

## 7. Hybrid Search in Manual Triage

BM25 and BGE-Small run in parallel.
Merged via Reciprocal Rank Fusion (k=60).

```
Search query → truncated first if long
    │
    ├── BM25 keyword search
    └── BGE-Small ONNX INT8 dense search
              │
              ▼
    RRF merge → top 10 results
    tagged: [semantic] [keyword] [hybrid]
```

---

## 8. LightGBM Tuning — Drift-Triggered, Not F1-Triggered

### Why F1 Trigger Was Wrong
F1 drops in QA environments signal new system bugs producing
new error patterns — not model drift. Auto-retraining on
a degraded data distribution teaches the model wrong patterns.
Blind retraining on F1 drop = production incident risk.

### Correct Trigger — Cosine Drift Detection
```
Every retrain cycle:
          │
          ▼
Compute cosine distance between:
  centroid of last 30 days error embeddings
  vs
  centroid of previous 30 days error embeddings
          │
    Distance > 0.25?
    (new error vocabulary detected)
    ┌─────┴─────┐
   YES          NO
    │            │
    ▼            ▼
Flag for human  Standard retrain
review first    with existing params
    │            unchanged
Human approves?
    │
    ▼
Run Optuna 50 trials
max 10 minutes
Bayesian search
    │
    ▼
Best params saved per project
LightGBM retrained
F1 score logged
```

### Key Change from v2
Auto-retrain on F1 drop → **removed**
Drift detection → **cosine distance threshold**
Human gate → **required before retraining on new distribution**
Optuna capability → **kept, trigger corrected**

---

## 9. Triage Aging

Pure timestamp logic in service-api. No model involved.

```
0–24h   → Fresh   (green)
1–3d    → Aging   (amber)
3–7d    → Stale   (orange)
7d+     → Breach  (red) → alert to project owner
```

Tracks both "To Investigate" and "Needs Expert Review" items.
Cannot be dismissed without classifying the item.

---

## 10. Release / Sprint Aggregate View

Pure aggregation in service-api. Groups by launch attribute.

| Gate | Condition |
|---|---|
| PASS | Pass rate ≥ 95% AND zero P0 failures |
| WARN | Pass rate 85–94% OR 1 P0 failure |
| BLOCK | Pass rate < 85% OR 2+ P0 failures |

BLOCK prevents CI deployment. WARN requires sign-off.

---

## 11. Launch Comparison Diff

Pure set comparison in service-api. No model involved.

```
Match by test item name across two launches:

Failed target only  → NEW FAILURE   (expanded default)
Failed base only    → FIXED
Failed both         → CONSISTENT
Different each run  → FLAKY
```

---

## Summary Table

| Feature | Service | Model / Logic | Key Change from v2 |
|---|---|---|---|
| Stack trace pre-processing | Both analyzers | Rule-based extractor | **New — was missing entirely** |
| Fast auto-analysis | Analyzer P1 | BM25 + scikit-learn | FlashRank depth 5, CPU load-shed added |
| Deep auto-analysis | Analyzer P2 | BGE-Small ONNX INT8 + FlashRank + LightGBM | **BGE-M3 → BGE-Small (CPU constraint)** |
| Reranker | P1 trim-first, P2 full | FlashRank TinyBERT ONNX | **bge-reranker → FlashRank (CPU latency)** |
| Vector search | Analyzer P2 | FAISS CPU via OpenSearch | **NumPy → FAISS SIMD (10–50x faster)** |
| Ranked suggestions | Analyzer P2 only | BGE-Small + FlashRank | Unchanged structure |
| Root cause clustering | Analyzer P2 only | BGE-Small + HDBSCAN | **Min 10 items, batch 32, BM25 pre-filter** |
| Flakiness detection | service-api | Deterministic (<10 runs) + PyOD (≥10 runs) | **Gate 3→10 runs, deterministic below gate** |
| Flakiness UI badge | UI leaf items only | Shown after ≥10 run history | **Gate 3→10 corrected** |
| LightGBM tuning | Analyzer P2 only | Optuna + cosine drift trigger | **F1 trigger removed → drift detection** |
| Confidence display | UI | Platt Scaling on LightGBM output | **Raw scores → calibrated probabilities** |
| Analysis source tag | UI every item | fast-AA / deep-AA / unresolved | Unchanged — mandatory |
| Triage aging | service-api | Timestamp logic | Unchanged |
| Release view | service-api | Aggregation by attribute | Unchanged |
| Launch diff | service-api | Set comparison by name | Unchanged |

---

## What Changed from v2 to v3 (Summary)

| v2 | v3 | Why |
|---|---|---|
| BGE-M3 (567M params) | BGE-Small-EN-v1.5 (33M params) ONNX INT8 | CPU deployment — BGE-M3 exceeds 10s timeout locally |
| bge-reranker-v2-m3 cross-encoder | FlashRank ms-marco-TinyBERT-L-2-v2 | Cross-encoder crushes CPU — FlashRank is <50ms ONNX-native |
| NumPy cosine similarity | FAISS CPU-only SIMD via OpenSearch | 10–50x faster on modern CPU AVX2/AVX-512 |
| No stack trace pre-processing | Extract exception + top 3 frames | Was missing entirely — critical for CPU efficiency |
| Flakiness gate ≥ 3 runs | Deterministic < 10, PyOD ≥ 10 | 3 runs is statistically invalid for anomaly detection |
| Optuna triggers on F1 < 0.80 | Optuna triggers on cosine drift > 0.25 with human gate | F1 drop = new bugs, not drift — blind retrain degrades model |
| No CPU load-shedding | Bypass reranker if CPU > 90% | Prevents local machine freeze on large failure events |
| Clustering min 5 items | Clustering min 10 items, batch 32, BM25 pre-filter | OOM risk on local RAM, coarse clusters below 10 |
| Raw LightGBM confidence | Platt Scaling calibrated confidence | Raw LightGBM scores are not true probabilities |
