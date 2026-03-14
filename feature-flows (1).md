# ReportPortal — Upgraded ML Feature Flows (v2)

> Combined approach: two separate analyzer service instances
> (priority-1 fast + priority-2 deep) with history-driven
> flakiness in service-api and UI badges on leaf items only.

> This document is the target architecture, not a statement of current repo behavior.
> To make the product follow this flow exactly, the repo needs three explicit refactors:
> multi-analyzer deployment in the default stack, per-item analysis-stage metadata,
> and migration of flakiness ownership from analyzer indexing into service-api.

---

## Architecture Overview

```
Failed items arrive from launch
          │
          ▼
┌─────────────────────────────────┐   ANALYZER_PRIORITY=1
│  Fast Analyzer (service 1)      │   AA_ENABLE_ASYNC_PIPELINE=true
│  BM25 + lightweight boosted     │   ANALYZER_SUGGEST=false
│  classifier                     │   ANALYZER_CLUSTER=false
│  Timeout: 2s                    │
│  Reranking: depth 10 or off     │   Rerank depth trimmed first
└─────────────────────────────────┘   if latency too high, disable
          │
    Confidence ≥ 70%?
    ┌─────┴─────┐
   YES          NO → unresolved items only
    │                     │
    ▼                     ▼
Auto-assign        ┌─────────────────────────────────┐  ANALYZER_PRIORITY=2
source: fast-AA    │  Deep Analyzer (service 2)      │  ANALYZER_SUGGEST=true
                   │  BGE-M3 + reranker + LightGBM   │  ANALYZER_CLUSTER=true
                   │  Timeout: 10s                   │  (if 5+ unresolved items)
                   └─────────────────────────────────┘
                             │
                       Confidence ≥ 55%?
                       ┌─────┴─────┐
                      YES          NO
                       │            │
                       ▼            ▼
                  Auto-assign   Needs Expert Review
                  source:       top 3 suggestions
                  deep-AA       triage aging starts
```

---

## 1. Fast Analyzer — Priority 1

### Purpose
Immediate defect assignment for known and recurring failures.
Handles ~65–70% of all failures within 2 seconds.

### Service Config
```
ANALYZER_PRIORITY=1
AA_ENABLE_ASYNC_PIPELINE=true
ANALYZER_SUGGEST=false
ANALYZER_CLUSTER=false
AA_PIPELINE_TIMEOUT_SECONDS=2
```

### Reranking Strategy
Reranking is the first thing to trim when latency is high:

```
Normal load:    rerank depth 10  → fast enough
High load:      rerank depth 5   → trim first
Latency breach: disable reranking entirely → BM25 only
```

### What It Does
- BM25 keyword retrieval + lightweight boosted classifier
- Intended to use the existing auto-analysis model path with latency-first tuning
- Runs on every failed item as soon as launch finishes
- Confidence ≥ 70% → auto-assign defect type, done
- Confidence < 70% → item handed off to deep analyzer
- No suggestions, no clustering — fast path only

### What Engineer Sees
```
✓ Auto-classified   Product Bug · Timing Issue    94%
  source: fast-AA   matched: Sprint 41 launch
```

---

## 2. Deep Analyzer — Priority 2

### Purpose
Semantic analysis of items the fast analyzer could not
confidently classify. Runs only on unresolved items.

### Service Config
```
ANALYZER_PRIORITY=2
AA_ENABLE_ASYNC_PIPELINE=true
ANALYZER_SUGGEST=true
ANALYZER_CLUSTER=true
AA_PIPELINE_TIMEOUT_SECONDS=10
```

### What It Does
- BGE-M3 hybrid retrieval (dense + sparse combined)
- Repo-supported reranker: top 30 candidates → reranked top 10
- Default compatible choice today is `BAAI/bge-reranker-base`; stronger rerankers are optional only if runtime compatibility is verified
- LightGBM scores candidates → probability per defect type
- Confidence ≥ 55% → auto-assign with source tag
- Confidence < 55% → stays unresolved, shows top 3 suggestions
- Clustering activates when 5+ unresolved items present

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

## 3. Analysis-Stage Metadata on Every Item

Every auto-classified item carries a source tag visible in the UI.
This is mandatory — not optional — so engineers calibrate trust correctly.

| Source Tag | Meaning |
|---|---|
| `fast-AA` | Classified by priority-1 fast analyzer |
| `deep-AA` | Classified by priority-2 deep analyzer |
| `unresolved` | Neither tier classified it — needs manual triage |

A 94% confidence result from `fast-AA` on a known recurring error
is different from a 58% result from `deep-AA` on a novel error.
Both are visible. Engineers know exactly what to trust.

### Implementation Note
- The repo already supports multi-analyzer fallback by exchange priority, but the default Docker stack still deploys only one analyzer service.
- The backend currently preserves analyzer-instance identity in events, but item APIs and UI do not yet expose `fast-AA`, `deep-AA`, and `unresolved` as first-class item metadata.
- This section is therefore a required implementation target, not current shipped behavior.

---

## 4. Flakiness Detection

### How It Works

Flakiness is a historical pattern — not a text inference problem.
The target design puts statistics and scoring in service-api.
PyOD scores the result. Analyzer services should not own this feature long-term.

```
Launch completes
          │
          ▼
service-api queries item history
from existing launch data
          │
          ▼
Compute 5 statistics per test item:
· pass_rate: fraction of passed runs
· alternation_rate: how often status flips
· streak_length: avg consecutive same-status runs
· recent_trend: last 5 runs vs overall rate
· std_dev: variance of binary outcomes
          │
          ▼
Gate: item must be a leaf test item
      (not a suite or folder row)
Gate: item must have ≥ 3 run history
      (below 3 → no badge shown at all)
          │
          ▼
PyOD IsolationForest scores
the 5-feature vector → 0 to 100
          │
    ┌─────┼─────┬─────┐
    ▼     ▼     ▼     ▼
  0-20  21-50 51-75 76-100
STABLE UNST- FLAKY CRIT-
       ABLE        ICAL
                    │
                    ▼
             Auto-quarantine
             Excluded from
             pass rate calc
             Alert sent
```

### Where Flakiness Lives
- Target state: statistics computed in **service-api** from launch history
- Target state: IsolationForest scoring runs in **service-api**
- Transitional note: current repo computes `flaky_score` and `is_quarantined` inside **service-auto-analyzer** during indexing, with PyOD IsolationForest plus heuristic fallback
- Transitional note: current repo persists flakiness fields on analyzer index documents rather than in a dedicated `{project}_flakiness` index

### UI Badge Rules
- Badge renders only on **leaf test items** — not suite rows
- Gated at `itemInfo.jsx:207` and `itemInfo.jsx:244`
- Badge fetch in `flakinessBadge.jsx:85` fires only when:
  - Item is a leaf node
  - Launch is completed (not in-progress)
  - Item has ≥ 3 run history
- Below 3 runs: no badge, no placeholder, nothing shown

### Implementation Note
- The current UI does not satisfy this yet: the shared item row renders flakiness for non-leaf rows unless explicit leaf gating is added.
- If this flow is mandated, leaf-only gating in the UI becomes required work, not optional polish.

### Score Thresholds

| Score | Label | Action |
|---|---|---|
| 0–20 | STABLE | No badge |
| 21–50 | UNSTABLE | Amber badge shown |
| 51–75 | FLAKY | Orange badge + engineer notified |
| 76–100 | CRITICALLY FLAKY | Red badge + auto-quarantine + alert |

### Quarantine Behaviour
- Quarantined items excluded from pass rate
- Both rates shown: `Pass rate: 91% (94% excl. 6 quarantined)`
- Engineer releases quarantine manually after fix
- Releasing resets history to zero

---

## 5. Root Cause Clustering

### How It Works

Only runs on the **deep analyzer (priority-2)**.
Never runs on fast analyzer (ANALYZER_CLUSTER=false on P1).
Minimum 5 unresolved items required before attempting.

```
Deep analyzer has N unresolved items
          │
    N ≥ 5?
    ┌─────┴─────┐
   YES          NO
    │            │
    ▼            ▼
Proceed      Skip clustering
             show items individually
    │
    ▼
BGE-M3 encodes all error messages
into dense vectors simultaneously
    │
    ▼
HDBSCAN clusters on vector space
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

### Thresholds
- < 5 items: clustering skipped entirely
- 5–9 items: attempted, results may be coarse
- 10+ items: reliable cluster quality

---

## 6. Ranked ML Suggestions

### How It Works

Only produced by **deep analyzer (priority-2)**.
ANALYZER_SUGGEST=false on fast tier — fast-AA never
generates suggestions for items it classifies.

```
Item unresolved after deep analyzer
(confidence < 55%)
          │
          ▼
BGE-M3 hybrid retrieval → top 30
bge-reranker → reranked top 10
LightGBM → probability per defect type
          │
          ▼
Top 3 shown to engineer:

1. Automation Bug — Timing Issue   87%  [semantic]  [Apply]
2. Product Bug — API Changed       61%  [keyword]   [Apply]
3. System Issue — DB Timeout       45%  [hybrid]    [Apply]
```

### Match Source Tags
- `semantic` — BGE-M3 dense match (meaning, not exact words)
- `keyword` — BM25 match (shared keywords)
- `hybrid` — both signals agreed (strongest signal)

---

## 7. Confidence Score Display

Every auto-classified item shows confidence and source tier.

| Confidence | Source | Visual |
|---|---|---|
| ≥ 90% | fast-AA or deep-AA | Green — trust it |
| 70–89% | fast-AA or deep-AA | Default — confident |
| 50–69% | deep-AA only | Amber border + "Review recommended" |
| < 50% | never auto-classified | Goes to suggestions |

Source tag shown on every item so engineers know
whether classification came from fast-AA or deep-AA.

---

## 8. Hybrid Search in Manual Triage

BM25 and BGE-M3 run in parallel during manual search.
Results merged via Reciprocal Rank Fusion (k=60).

```
Search query
    │
    ├── BM25 keyword search
    └── BGE-M3 dense search
              │
              ▼
    RRF merge → top 10 results
    each tagged: [semantic] [keyword] [hybrid]
```

---

## 9. Optuna Hyperparameter Auto-Tuning

Applies to LightGBM in **deep analyzer only**.
Fast analyzer uses scikit-learn — Optuna not involved.

```
Deep analyzer model retrain triggered
          │
    F1 score < 0.80?
    ┌─────┴─────┐
   YES          NO
    │            │
    ▼            ▼
Optuna 50 trials  Standard retrain
max 10 minutes    unchanged params
Bayesian search
    │
    ▼
Per-project best params saved
LightGBM retrained with them
```

Runs async. Does not block analysis. Per-project only.

---

## 10. Triage Aging

Pure timestamp logic in service-api. No model involved.
Tracks every item in "To Investigate" or "Needs Expert Review".

```
0–24h   → Fresh   (green)
1–3d    → Aging   (amber)
3–7d    → Stale   (orange)
7d+     → Breach  (red) → alert to project owner
```

Cannot be dismissed without classifying the item.

---

## 11. Release / Sprint Aggregate View

Pure aggregation in service-api. Groups launches by attribute.

| Gate | Condition |
|---|---|
| PASS | Pass rate ≥ 95% AND zero P0 failures |
| WARN | Pass rate 85–94% OR 1 P0 failure |
| BLOCK | Pass rate < 85% OR 2+ P0 failures |

BLOCK prevents CI deployment. WARN requires sign-off.

---

## 12. Launch Comparison Diff

Pure set comparison in service-api. No model involved.

```
Match by test item name across two launches:

Failed target only  → NEW FAILURE   (expanded by default)
Failed base only    → FIXED
Failed both         → CONSISTENT
Different each run  → FLAKY
```

---

## Summary Table

| Feature | Service | Model / Logic |
|---|---|---|
| Fast auto-analysis | Analyzer P1 | BM25 + lightweight boosted classifier |
| Deep auto-analysis | Analyzer P2 | BGE-M3 + repo-supported reranker + LightGBM |
| Ranked suggestions | Analyzer P2 only | BGE-M3 + reranker (SUGGEST=true on P2) |
| Root cause clustering | Analyzer P2 only | BGE-M3 + HDBSCAN (CLUSTER=true on P2) |
| Hybrid manual search | Both analyzers | BGE-M3 + BM25 via RRF |
| Flakiness detection | service-api target | History stats + PyOD IsolationForest |
| Flakiness UI badge | UI leaf items only | Shown after 3+ run history |
| Optuna tuning | Analyzer P2 only | LightGBM per-project |
| Analysis source tag | UI on every item | fast-AA / deep-AA / unresolved |
| Triage aging | service-api | Timestamp logic only |
| Release view | service-api | Aggregation by launch attribute |
| Launch diff | service-api | Set comparison by item name |

---

## Repo Alignment Required

1. Deploy two analyzer instances in the default stack so exchange-priority fallback becomes active instead of theoretical.
2. Persist per-item analysis-stage metadata through service-api and surface it in the UI as `fast-AA`, `deep-AA`, or `unresolved`.
3. Expose per-item confidence for auto-analysis results, not only suggestion cards.
4. Gate flakiness badges to completed leaf test items with at least 3-run history.
5. Decide whether flakiness ownership moves fully into service-api now, or whether analyzer-side scoring remains as a temporary bridge during migration.
