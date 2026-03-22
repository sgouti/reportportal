---
name: reportportal-improvements
description: >
  Implements the ReportPortal reporting improvement plan across 4 phases:
  smart failure cards, flakiness dashboards, alert engine, and semantic
  failure search. Use this skill whenever the user wants to build, scaffold,
  or implement any part of the ReportPortal improvement plan — including UI
  mockups, backend services, ML analyser components, API endpoints, or
  Docker dev setup. Triggers on: "implement phase", "build the failure card",
  "set up the analyser", "scaffold the alert engine", "set up docker dev",
  "implement semantic search", or any reference to the improvement plan.
---

# ReportPortal Improvements Skill

Guides implementation of the 4-phase ReportPortal reporting improvement plan.
Each phase has its own UI-first → backend → API ordering.

## Folder structure

```
reportportal-improvements/
├── SKILL.md                    ← you are here
├── references/
│   ├── phase1-failure-ui.md    ← failure card + cluster UI specs
│   ├── phase2-dashboard-ui.md  ← flakiness + trend + duration specs
│   ├── phase3-alerts-ui.md     ← alerts, digest, share link specs
│   ├── phase4-search-ui.md     ← semantic search + sidebar specs
│   └── api-reference.md        ← all API contracts in one place
├── scripts/
│   ├── log_parser.py           ← parses raw stack traces → structured failure
│   ├── clusterer.py            ← MiniLM + HDBSCAN failure clustering
│   ├── flakiness.py            ← flakiness % + trend calculator
│   ├── alert_engine.py         ← rule evaluator + dispatcher
│   ├── search_index.py         ← FAISS index build + query
│   ├── hybrid_search.py        ← BM25 + FAISS RRF merger
│   └── docker/
│       ├── docker-compose.dev.yml   ← bind-mount dev stack
│       └── Dockerfile.dev           ← dev image with hot reload
└── assets/
    └── ml-stack.md             ← model choices, sizes, rationale
```

---

## How to use this skill

### Step 1 — Identify which phase the user wants

| User says | Go to |
|---|---|
| "failure card", "cluster view", "smart summary" | Phase 1 → `references/phase1-failure-ui.md` |
| "flakiness", "pass rate trend", "duration" | Phase 2 → `references/phase2-dashboard-ui.md` |
| "alert", "digest", "shareable link" | Phase 3 → `references/phase3-alerts-ui.md` |
| "semantic search", "similar failures", "search bar" | Phase 4 → `references/phase4-search-ui.md` |
| "all APIs", "API contract" | `references/api-reference.md` |
| "docker", "dev setup", "hot reload", "local dev" | `scripts/docker/` |
| "ML models", "analyser stack" | `assets/ml-stack.md` |

### Step 2 — Always do UI first, then backend, then API

For every phase:
1. Show the ASCII UI mockup from the reference file
2. Scaffold the backend script from `scripts/`
3. Define the API contract from `references/api-reference.md`

### Step 3 — When implementing, run the relevant script

```bash
# Install ML deps first (CPU only, no GPU needed)
pip install sentence-transformers faiss-cpu hdbscan rank-bm25 fastapi uvicorn

# Run a specific backend component
python scripts/log_parser.py          # test failure parsing
python scripts/clusterer.py           # test clustering on sample logs
python scripts/search_index.py        # build FAISS index

# Start dev stack (bind mount — edit locally, see in Docker)
docker compose -f scripts/docker/docker-compose.dev.yml up
```

---

## Phase overview

### Phase 1 — Smart failure reporting (Weeks 1–4)
**Problem:** Raw stack trace dumps, no grouping, no diff view.
**Deliverables:** Failure summary card, expected/actual diff, auto-cluster view.
**Key scripts:** `log_parser.py`, `clusterer.py`
**Read:** `references/phase1-failure-ui.md`

### Phase 2 — Dashboard & trend reporting (Weeks 5–10)
**Problem:** No flakiness view, launch-scoped trends only, no duration tracking.
**Deliverables:** Flakiness dashboard, date-range trend picker, duration trend table.
**Key scripts:** `flakiness.py`
**Read:** `references/phase2-dashboard-ui.md`

### Phase 3 — Alerts & stakeholder sharing (Weeks 11–16)
**Problem:** Blunt email-only alerts, no shareable links, no scheduled digests.
**Deliverables:** Rule-based alerts (Slack/email), read-only share links, digest scheduler.
**Key scripts:** `alert_engine.py`
**Read:** `references/phase3-alerts-ui.md`

### Phase 4 — Semantic failure search (Weeks 17–22)
**Problem:** Only keyword search; no discovery of similar historical failures.
**Deliverables:** BM25+FAISS hybrid search bar, similar-failures sidebar.
**Key scripts:** `search_index.py`, `hybrid_search.py`
**Read:** `references/phase4-search-ui.md`

---

## ML analyser stack (quick ref)

All models are CPU-only, no external service needed.

| Model | Size | Role |
|---|---|---|
| `all-MiniLM-L6-v2` | ~80 MB | Embeds failure messages for semantic similarity |
| `FAISS IndexFlatIP` | ~5 MB + index | Vector similarity search over historical failures |
| `rank-bm25` | ~1 MB | Keyword match on error codes / class names |
| `HDBSCAN` | ~3 MB | Auto-clusters failures within a launch (no k needed) |

See `assets/ml-stack.md` for full rationale and tuning notes.

---

## Docker dev setup (inner loop)

Edit locally → changes sync into container → hot reload → validate in browser.

```
your editor  →  bind mount  →  container  →  browser (localhost:3000 / :8000)
```

Full config in `scripts/docker/docker-compose.dev.yml`.
Frontend: Vite hot reload. Backend: `uvicorn --reload`.