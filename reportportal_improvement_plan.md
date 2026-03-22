# ReportPortal — Improvement Implementation Plan

> Scope: Reporting features + lightweight ML analyser for QA teams
> Stack: React (frontend) · Python/FastAPI (backend) · PostgreSQL · FAISS · sentence-transformers

## Mandatory Delivery Model

This plan must be executed in a fixed sequence for every feature and every phase. The order is mandatory and must not be skipped.

### Delivery Principles

1. Local-first containerised development
2. UI first
3. Backend second
4. Integration last

### Stage 1 — UI First With Dummy Data

- Build the UI in `service-ui/app` first.
- Use dummy data only. No API wiring, no backend dependency, no partial integration.
- Validate the UX, layout, states, empty cases, error states, and navigation using local fixtures or request stubs.
- Present the UI to the user for approval before any backend implementation starts.

### Stage 2 — Backend After UI Approval

- Start backend work only after the UI is approved.
- Implement the service contracts required by the approved UI, not a larger speculative API surface.
- Keep backend validation isolated from the UI where possible until the backend behavior is approved.
- Present backend behavior, payload shape, persistence rules, and runtime behavior for approval before integration starts.

### Stage 3 — Integration After Backend Approval

- Connect the approved UI to the approved backend only after both parts are accepted.
- Replace dummy data incrementally and keep the approved UI behavior stable.
- Run regression checks on loading, empty, error, and partial-data states during wiring.

### Approval Gates

- Gate A: UI approval is required before backend implementation.
- Gate B: Backend approval is required before frontend-backend integration.
- Gate C: Integration is complete only after end-to-end validation in the local Docker-based environment.

### Local-First Containerised Development

- Start every feature in the local development environment before thinking about shared or remote environments.
- Keep shared platform dependencies in containers from the repository root `docker-compose.yml` so the runtime is reproducible on every machine.
- Use containers for infrastructure concerns first: database, messaging, dependent services, and final integration validation.
- Keep the UI feedback loop fast by running `service-ui/app` locally with `npm run dev` on `http://localhost:3000` while the platform services remain containerised.
- During Stage 1, use dummy data or request stubs and avoid any requirement for a live backend implementation.
- Do not couple early UI work to incomplete API containers; integration happens only in Stage 3 after approval.
- Treat Docker as the source of truth for runtime parity and local development as the source of truth for iteration speed.

### Modern UI Direction

- The first deliverable for each feature must look like a modern product surface, not only a functional placeholder.
- Prefer clean information hierarchy, deliberate spacing, strong typography, refined color contrast, and clear status signaling.
- Use modern interaction patterns already supported by the stack, including smooth state transitions and purposeful motion where it improves comprehension.
- Avoid visually outdated admin-panel patterns when a clearer and more polished interaction can be delivered within the current design system.
- Design all approved UI states before backend work: loading, empty, populated, partial, error, and success feedback.
- Keep the UI responsive for desktop and laptop widths from the first pass instead of treating responsiveness as a final polish task.
- Reuse existing frontend capabilities where practical, including animation support already available in the `service-ui/app` stack.

### Recommended UI-First Mechanics

- Prefer local fixture files, selector-friendly component states, and API response stubs for early UI development.
- Reuse the existing frontend test stack and request mocking utilities where practical, including `axios-mock-adapter` in `service-ui/app`.
- Define the contract from the approved UI state shapes first, then implement backend endpoints to match those shapes.

---

## Table of Contents

1. [Mandatory Delivery Model](#mandatory-delivery-model)
2. [Phase 1 — Failure Reporting UI + Smart Summary](#phase-1)
3. [Phase 2 — Dashboard & Trend Reporting](#phase-2)
4. [Phase 3 — Alerts & Stakeholder Sharing](#phase-3)
5. [Phase 4 — Semantic Failure Search](#phase-4)
6. [ML Analyser Stack](#ml-analyser-stack)
7. [API Reference](#api-reference)

---

## Phase 1 — Failure Reporting UI + Smart Summary {#phase-1}

**Goal:** Replace raw stack trace dumps with a readable, structured failure card. Auto-cluster similar failures within a launch.

**Timeline:** Weeks 1–4

**Execution rule:** Complete the UI with dummy data first, pause for user approval, then implement backend parsing and clustering, pause for approval again, and only then wire the UI to live APIs.

**Stage breakdown:**
- Stage 1A: `1.1` and `1.2` as UI-only flows with dummy data.
- Stage 1B: `1.3`, `1.4`, and `1.5` only after UI approval.
- Stage 1C: Replace dummy data with live launch failure and cluster responses only after backend approval.

---

### 1.1 UI Mockup — Smart Failure Card

Current state: a failed test opens a raw log panel with the full stack trace.
Proposed: a structured card with the key failure surfaced at the top.

```
┌─────────────────────────────────────────────────────────────────┐
│  FAILED  checkout_test.py::test_payment_gateway                 │
│  Duration: 1.2s  ·  Launch #142  ·  2025-03-21 09:14           │
├─────────────────────────────────────────────────────────────────┤
│  Failure summary                                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  AssertionError: Expected 200, got 502                    │  │
│  │  at checkout/payment.py : line 88  ← root line           │  │
│  │                                                           │  │
│  │  Expected   200                                           │  │
│  │  Actual     502                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Similar failures (3)                           [ View all → ] │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────┐  │
│  │ test_refund #138 │ │ test_void   #135 │ │ test_auth #131 │  │
│  │ Same error line  │ │ Same error line  │ │ 502 pattern    │  │
│  └──────────────────┘ └──────────────────┘ └────────────────┘  │
│                                                                 │
│  [ Mark as: Product Bug | Automation Bug | System Issue ]      │
│  [ Link Jira ticket ]    [ View raw log ↓ ]                    │
└─────────────────────────────────────────────────────────────────┘
```

**Key changes from current UI:**
- Root failure line highlighted, not buried in a 200-line trace
- Expected vs actual diff shown inline for assertion errors
- Similar failures shown as cards (from FAISS search, see Phase 4)
- Raw log collapsed by default — expandable on demand

---

### 1.2 UI Mockup — Failure Cluster View (within a launch)

```
Launch #142  ·  87 tests  ·  61 passed  ·  26 failed
─────────────────────────────────────────────────────

  Failure clusters                         [ Sort: by count ▾ ]

  ┌──────────────────────────────────────────────────────────┐
  │  Cluster A  ·  14 tests                    [Expand ▾]   │
  │  502 Bad Gateway — payment.py line 88                    │
  │  Likely cause: payment service down                      │
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │  Cluster B  ·  8 tests                     [Expand ▾]   │
  │  AssertionError: expected user role "admin"              │
  │  Likely cause: test data / fixture issue                 │
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │  Unclustered  ·  4 tests                   [Expand ▾]   │
  │  Novel failures — no historical match found              │
  └──────────────────────────────────────────────────────────┘
```

**Rules for clustering:**
- Groups are formed by HDBSCAN on MiniLM embeddings of the failure message + root line
- Cluster label = most frequent error class + file location
- "Likely cause" = top BM25 keyword from cluster members
- Unclustered = HDBSCAN noise points (no similar neighbours)

---

### 1.3 Backend — Log Parser

**File:** `analyser/log_parser.py`

```python
import re
from dataclasses import dataclass

FRAMEWORK_PACKAGES = {
    "pytest", "unittest", "_pytest", "pluggy",
    "java.lang.reflect", "sun.reflect", "org.junit",
    "com.google.common"
}

@dataclass
class ParsedFailure:
    exception_type: str        # e.g. "AssertionError"
    message: str               # e.g. "Expected 200, got 502"
    root_file: str             # first non-framework frame file
    root_line: int             # line number
    expected: str | None       # extracted from assertion message
    actual: str | None
    raw_log: str

def parse(raw_log: str) -> ParsedFailure:
    lines = raw_log.strip().splitlines()

    exception_type, message = _extract_exception(lines)
    root_file, root_line = _find_root_frame(lines)
    expected, actual = _extract_diff(message)

    return ParsedFailure(
        exception_type=exception_type,
        message=message,
        root_file=root_file,
        root_line=root_line,
        expected=expected,
        actual=actual,
        raw_log=raw_log
    )

def _extract_exception(lines: list[str]) -> tuple[str, str]:
    for line in reversed(lines):
        m = re.match(r'^(\w[\w.]*(?:Error|Exception|Failure)): (.+)$', line)
        if m:
            return m.group(1), m.group(2)
    return "UnknownError", lines[-1] if lines else ""

def _find_root_frame(lines: list[str]) -> tuple[str, int]:
    for line in lines:
        m = re.match(r'\s+File "(.+)", line (\d+)', line)
        if m:
            filepath = m.group(1)
            if not any(pkg in filepath for pkg in FRAMEWORK_PACKAGES):
                return filepath.split("/")[-1], int(m.group(2))
    return "unknown", 0

def _extract_diff(message: str) -> tuple[str | None, str | None]:
    # "Expected X, got Y" / "expected X but was Y"
    m = re.search(r'[Ee]xpected (.+?)(?:,| but was) (.+)', message)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None
```

---

### 1.4 Backend — Failure Clusterer

**File:** `analyser/clusterer.py`

```python
from sentence_transformers import SentenceTransformer
import hdbscan
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")  # ~80MB, CPU-only

def embed_failures(failure_messages: list[str]) -> np.ndarray:
    """
    Each message = exception_type + ": " + message (short, <100 chars usually).
    MiniLM handles this size optimally — no chunking needed.
    """
    return model.encode(failure_messages, batch_size=64, show_progress_bar=False)

def cluster(embeddings: np.ndarray, min_cluster_size: int = 2) -> np.ndarray:
    """
    HDBSCAN — no need to specify k.
    min_cluster_size=2 means even 2 similar failures form a cluster.
    Returns array of cluster labels (-1 = noise/unclustered).
    """
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=1,
        metric="euclidean"
    )
    return clusterer.fit_predict(embeddings)

def build_clusters(failures: list[dict]) -> list[dict]:
    """
    failures: list of { id, message, root_file, root_line }
    Returns: list of cluster groups with label and members
    """
    messages = [f"{f['exception_type']}: {f['message']}" for f in failures]
    embeddings = embed_failures(messages)
    labels = cluster(embeddings)

    groups: dict[int, list] = {}
    for i, label in enumerate(labels):
        groups.setdefault(int(label), []).append(failures[i])

    result = []
    for label, members in sorted(groups.items(), key=lambda x: -len(x[1])):
        result.append({
            "cluster_id": label,
            "is_novel": label == -1,
            "count": len(members),
            "label": _cluster_label(members),
            "members": members
        })
    return result

def _cluster_label(members: list[dict]) -> str:
    # Most common exception type + first member's root file
    types = [m["exception_type"] for m in members]
    top_type = max(set(types), key=types.count)
    root = members[0].get("root_file", "")
    return f"{top_type} — {root}" if root else top_type
```

---

### 1.5 APIs — Phase 1

#### `GET /api/v2/launch/{launch_id}/failures`

Returns parsed failure cards for all failed tests in a launch.

**Response:**
```json
{
  "launch_id": "142",
  "total_failed": 26,
  "failures": [
    {
      "test_id": "t_8821",
      "test_name": "checkout_test.py::test_payment_gateway",
      "duration_ms": 1200,
      "exception_type": "AssertionError",
      "message": "Expected 200, got 502",
      "root_file": "payment.py",
      "root_line": 88,
      "expected": "200",
      "actual": "502",
      "cluster_id": 0,
      "similar_count": 3
    }
  ]
}
```

---

#### `GET /api/v2/launch/{launch_id}/clusters`

Returns failure clusters for a launch.

**Response:**
```json
{
  "launch_id": "142",
  "clusters": [
    {
      "cluster_id": 0,
      "label": "AssertionError — payment.py",
      "count": 14,
      "is_novel": false,
      "members": ["t_8821", "t_8834", "..."]
    },
    {
      "cluster_id": -1,
      "label": "Unclustered (novel)",
      "count": 4,
      "is_novel": true,
      "members": ["t_8900", "..."]
    }
  ]
}
```

---

## Phase 2 — Dashboard & Trend Reporting {#phase-2}

**Goal:** Flakiness dashboard, time-range trend picker, test duration tracking.

**Timeline:** Weeks 5–10

**Execution rule:** Deliver dashboard screens with dummy trend data first, wait for user approval, then implement analytics and APIs, and only after approval connect dashboard widgets to live data.

**Stage breakdown:**
- Stage 2A: `2.1`, `2.2`, and `2.3` as UI-only widgets with mock datasets.
- Stage 2B: `2.4` and `2.5` only after UI approval.
- Stage 2C: Integrate filters, shared date context, and live metrics only after backend approval.

---

### 2.1 UI Mockup — Flakiness Dashboard

```
Flakiness Report  ·  Project: checkout-service
──────────────────────────────────────────────────

  Period [ Last 30 days ▾ ]    Min flakiness % [ 5% ▾ ]

  ┌──────────────────────────────────────────────────────────────┐
  │  Flakiness rate over time                                    │
  │                                                              │
  │  12% ┤                    *                                  │
  │   8% ┤         *    *  *    *   *                            │
  │   4% ┤   *  *                        *   *                  │
  │   0% ┼──────────────────────────────────────────────────    │
  │       Mar 1   Mar 7   Mar 14   Mar 21  (today)              │
  └──────────────────────────────────────────────────────────────┘

  Top flaky tests                             [ Export CSV ]

  ┌─────────────────────────────────┬────────┬───────┬─────────┐
  │ Test name                       │ Flaky% │ Fails │  Trend  │
  ├─────────────────────────────────┼────────┼───────┼─────────┤
  │ test_payment_retry              │  38%   │  8/21 │   ↑ ↑  │
  │ test_session_timeout            │  24%   │  5/21 │   →    │
  │ test_search_results_order       │  14%   │  3/21 │   ↓    │
  └─────────────────────────────────┴────────┴───────┴─────────┘
```

**Flakiness definition used:** a test is flaky if it has both a pass and a fail result within the selected time window, without a code change between them.

---

### 2.2 UI Mockup — Time-Range Trend Picker

```
Pass rate trend

  [ ← ]  Mar 2025  [ → ]    Preset: [ Last 7d | 30d | 90d | Custom ]

  ┌──────────────────────────────────────────────────────────────┐
  │  100% ┤                                                      │
  │   90% ┤     ████████████████████████████████████            │
  │   80% ┤  ██                                      ██         │
  │   70% ┤                                                      │
  │        Mar 1   Mar 7   Mar 14   Mar 21                      │
  └──────────────────────────────────────────────────────────────┘

  Compare to previous period  [ ON/OFF ]
```

**Key change:** All trend widgets get a shared date range context — change it once, all charts on the dashboard update.

---

### 2.3 UI Mockup — Test Duration Trends

```
Slowest tests (by avg duration, last 30d)

  ┌──────────────────────────────────┬────────┬──────────┬──────┐
  │ Test name                        │ Avg    │ 30d ago  │ Δ    │
  ├──────────────────────────────────┼────────┼──────────┼──────┤
  │ test_full_checkout_e2e           │ 14.2s  │  9.1s    │ +56% │  ← flag
  │ test_report_pdf_export           │  8.8s  │  8.6s    │  +2% │
  │ test_user_bulk_import            │  6.1s  │  7.2s    │ -15% │
  └──────────────────────────────────┴────────┴──────────┴──────┘
```

Tests with >20% duration increase flagged in red automatically.

---

### 2.4 Backend — Flakiness Calculator

**File:** `analytics/flakiness.py`

```python
from collections import defaultdict
from datetime import datetime, timedelta
from db import get_test_results  # returns list of {test_id, name, status, launched_at}

def compute_flakiness(project_id: str, days: int = 30) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=days)
    results = get_test_results(project_id, since=since)

    # Group by test_id
    by_test: dict[str, list] = defaultdict(list)
    for r in results:
        by_test[r["test_id"]].append(r)

    flaky = []
    for test_id, runs in by_test.items():
        statuses = {r["status"] for r in runs}
        if "PASSED" in statuses and "FAILED" in statuses:
            total = len(runs)
            fails = sum(1 for r in runs if r["status"] == "FAILED")
            flaky.append({
                "test_id": test_id,
                "test_name": runs[0]["name"],
                "flakiness_pct": round(fails / total * 100, 1),
                "failed_runs": fails,
                "total_runs": total,
                "trend": _compute_trend(runs, days)
            })

    return sorted(flaky, key=lambda x: -x["flakiness_pct"])

def _compute_trend(runs: list[dict], days: int) -> str:
    mid = datetime.utcnow() - timedelta(days=days // 2)
    first_half = [r for r in runs if r["launched_at"] < mid]
    second_half = [r for r in runs if r["launched_at"] >= mid]
    if not first_half or not second_half:
        return "neutral"
    f1 = sum(1 for r in first_half if r["status"] == "FAILED") / len(first_half)
    f2 = sum(1 for r in second_half if r["status"] == "FAILED") / len(second_half)
    if f2 > f1 + 0.05:
        return "worsening"
    if f2 < f1 - 0.05:
        return "improving"
    return "stable"
```

---

### 2.5 APIs — Phase 2

#### `GET /api/v2/project/{project_id}/flakiness`

**Query params:** `days=30`, `min_pct=5`, `page=1`, `limit=50`

**Response:**
```json
{
  "period_days": 30,
  "flaky_test_count": 12,
  "project_flakiness_pct": 8.4,
  "tests": [
    {
      "test_id": "t_8821",
      "test_name": "test_payment_retry",
      "flakiness_pct": 38.1,
      "failed_runs": 8,
      "total_runs": 21,
      "trend": "worsening"
    }
  ]
}
```

---

#### `GET /api/v2/project/{project_id}/pass-rate`

**Query params:** `from=2025-03-01`, `to=2025-03-21`, `granularity=day`

**Response:**
```json
{
  "from": "2025-03-01",
  "to": "2025-03-21",
  "granularity": "day",
  "series": [
    { "date": "2025-03-01", "pass_rate": 91.2, "total": 320, "passed": 292 },
    { "date": "2025-03-02", "pass_rate": 88.0, "total": 318, "passed": 280 }
  ]
}
```

---

#### `GET /api/v2/project/{project_id}/duration-trends`

**Query params:** `days=30`, `flag_pct_increase=20`

**Response:**
```json
{
  "tests": [
    {
      "test_id": "t_9001",
      "test_name": "test_full_checkout_e2e",
      "avg_duration_ms": 14200,
      "prev_avg_duration_ms": 9100,
      "delta_pct": 56.0,
      "flagged": true
    }
  ]
}
```

---

## Phase 3 — Alerts & Stakeholder Sharing {#phase-3}

**Goal:** Rule-based alert engine, scheduled digest reports, read-only shareable dashboard links.

**Timeline:** Weeks 11–16

**Execution rule:** Prototype alert and sharing flows in the UI first with dummy rules, fake recipients, and generated sample links. Start backend only after the UI flow is approved, then integrate only after backend approval.

**Stage breakdown:**
- Stage 3A: `3.1`, `3.2`, and `3.3` as UI-only configuration flows backed by dummy state.
- Stage 3B: `3.4`, `3.5`, and `3.6` only after UI approval.
- Stage 3C: Wire rule persistence, alert dispatch status, and share-link generation only after backend approval.

---

### 3.1 UI Mockup — Alert Rule Builder

```
Alerts  ·  Project: checkout-service       [ + New rule ]
─────────────────────────────────────────────────────────

  ┌────────────────────────────────────────────────────────────┐
  │  Rule: Pass rate drop                            [ Active ]│
  │                                                            │
  │  Condition:  Pass rate  [ < ▾ ]  [ 80 ]  %                │
  │  Window:     [ Any launch ▾ ]                              │
  │  Notify:     [ Slack ▾ ]  #qa-alerts                       │
  │              [ Email ▾ ]  team@company.com                 │
  │                                                      [Save]│
  └────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────┐
  │  Rule: New failure cluster                       [ Active ]│
  │                                                            │
  │  Condition:  Novel cluster detected in launch              │
  │  Notify:     [ Slack ▾ ]  #qa-alerts                       │
  │                                                      [Save]│
  └────────────────────────────────────────────────────────────┘
```

---

### 3.2 UI Mockup — Scheduled Digest Config

```
Scheduled reports  ·  Project: checkout-service

  ┌────────────────────────────────────────────────────────────┐
  │  Daily summary digest                                      │
  │                                                            │
  │  Schedule:    [ Daily ▾ ]   at  [ 08:00 ▾ ]               │
  │  Recipients:  team@company.com, pm@company.com             │
  │  Include:     [x] Pass rate   [x] Flaky tests              │
  │               [x] New failures  [ ] Duration trends        │
  │                                                      [Save]│
  └────────────────────────────────────────────────────────────┘
```

---

### 3.3 UI Mockup — Shareable Dashboard Link

```
Share dashboard

  ┌────────────────────────────────────────────────────────────┐
  │  Read-only public link                                     │
  │                                                            │
  │  https://reportportal.io/share/abc123xyz  [ Copy ]         │
  │                                                            │
  │  Expires:  [ Never ▾ ]                                     │
  │  Scope:    [ This dashboard only ▾ ]                       │
  │                                                            │
  │  [ Revoke link ]                                           │
  └────────────────────────────────────────────────────────────┘
```

---

### 3.4 Backend — Alert Engine

**File:** `alerts/engine.py`

```python
from dataclasses import dataclass
from enum import Enum
from db import get_alert_rules, save_alert_event
from notifiers import send_slack, send_email

class AlertCondition(Enum):
    PASS_RATE_BELOW = "pass_rate_below"
    NOVEL_CLUSTER_DETECTED = "novel_cluster_detected"
    FLAKINESS_ABOVE = "flakiness_above"

@dataclass
class AlertRule:
    rule_id: str
    project_id: str
    condition: AlertCondition
    threshold: float | None
    channels: list[dict]   # [{type: "slack", target: "#qa-alerts"}]
    active: bool

def evaluate_on_launch_complete(launch_result: dict):
    """Called by event hook when a launch finishes."""
    project_id = launch_result["project_id"]
    rules = get_alert_rules(project_id)

    for rule in rules:
        if not rule.active:
            continue
        fired, context = _check(rule, launch_result)
        if fired:
            _dispatch(rule, context)
            save_alert_event(rule.rule_id, launch_result["launch_id"], context)

def _check(rule: AlertRule, launch: dict) -> tuple[bool, dict]:
    if rule.condition == AlertCondition.PASS_RATE_BELOW:
        rate = launch["passed"] / launch["total"] * 100
        if rate < rule.threshold:
            return True, {"pass_rate": round(rate, 1), "threshold": rule.threshold}

    if rule.condition == AlertCondition.NOVEL_CLUSTER_DETECTED:
        if launch.get("novel_cluster_count", 0) > 0:
            return True, {"novel_clusters": launch["novel_cluster_count"]}

    if rule.condition == AlertCondition.FLAKINESS_ABOVE:
        if launch.get("flakiness_pct", 0) > rule.threshold:
            return True, {"flakiness_pct": launch["flakiness_pct"]}

    return False, {}

def _dispatch(rule: AlertRule, context: dict):
    message = _format_message(rule, context)
    for channel in rule.channels:
        if channel["type"] == "slack":
            send_slack(channel["target"], message)
        elif channel["type"] == "email":
            send_email(channel["target"], subject="ReportPortal alert", body=message)

def _format_message(rule: AlertRule, context: dict) -> str:
    if rule.condition == AlertCondition.PASS_RATE_BELOW:
        return (f"Pass rate dropped to {context['pass_rate']}% "
                f"(threshold: {context['threshold']}%)")
    if rule.condition == AlertCondition.NOVEL_CLUSTER_DETECTED:
        return f"{context['novel_clusters']} new failure pattern(s) detected."
    if rule.condition == AlertCondition.FLAKINESS_ABOVE:
        return f"Flakiness reached {context['flakiness_pct']}% this launch."
    return "Alert triggered."
```

---

### 3.5 Backend — Shareable Link Generator

**File:** `sharing/links.py`

```python
import secrets
from datetime import datetime, timedelta
from db import save_share_token, get_share_token

def create_share_link(dashboard_id: str, user_id: str, expires_days: int | None = None) -> str:
    token = secrets.token_urlsafe(16)
    expires_at = (datetime.utcnow() + timedelta(days=expires_days)) if expires_days else None
    save_share_token({
        "token": token,
        "dashboard_id": dashboard_id,
        "created_by": user_id,
        "expires_at": expires_at,
        "revoked": False
    })
    return f"https://reportportal.io/share/{token}"

def resolve_share_token(token: str) -> dict | None:
    record = get_share_token(token)
    if not record or record["revoked"]:
        return None
    if record["expires_at"] and datetime.utcnow() > record["expires_at"]:
        return None
    return {"dashboard_id": record["dashboard_id"]}
```

---

### 3.6 APIs — Phase 3

#### `POST /api/v2/project/{project_id}/alerts`

**Request:**
```json
{
  "condition": "pass_rate_below",
  "threshold": 80,
  "channels": [
    { "type": "slack", "target": "#qa-alerts" },
    { "type": "email", "target": "team@company.com" }
  ]
}
```

**Response:** `201 Created` with `{ "rule_id": "r_001" }`

---

#### `POST /api/v2/dashboard/{dashboard_id}/share`

**Request:**
```json
{ "expires_days": null }
```

**Response:**
```json
{
  "share_url": "https://reportportal.io/share/abc123xyz",
  "expires_at": null
}
```

---

#### `GET /share/{token}`

Public endpoint — no auth required. Returns read-only dashboard data.

**Response:** Same as `GET /api/v2/dashboard/{id}` but with `read_only: true` flag.

---

#### `POST /api/v2/project/{project_id}/digest`

**Request:**
```json
{
  "schedule": "daily",
  "time": "08:00",
  "recipients": ["team@company.com"],
  "include": ["pass_rate", "flaky_tests", "new_failures"]
}
```

**Response:** `201 Created`

---

## Phase 4 — Semantic Failure Search {#phase-4}

**Goal:** BM25 + FAISS hybrid search over all historical failures. Similar failures sidebar on the failure card.

**Timeline:** Weeks 17–22

**Execution rule:** Build and approve the search UX first using dummy indexed results, then implement indexing and ranking services, and only after approval connect search interactions to the live analyzer stack.

**Stage breakdown:**
- Stage 4A: `4.1` and `4.2` as UI-only search experiences with stubbed results.
- Stage 4B: `4.3`, `4.4`, and `4.5` only after UI approval.
- Stage 4C: Integrate live semantic search, ranking, and sidebar similarity data only after backend approval.

---

### 4.1 UI Mockup — Semantic Search Bar

```
Search failures  ·  All projects ▾

  ┌─────────────────────────────────────────────────────────────┐
  │  payment service timeout                           [Search] │
  └─────────────────────────────────────────────────────────────┘

  Results  (23 matches, ranked by relevance)

  ┌───────────────────────────────────────────────────────────┐
  │  AssertionError: connection timeout after 30s             │
  │  test_payment_gateway  ·  Launch #138  ·  Mar 15          │
  │  Fixed under: JIRA-4421  (by @ravi, Mar 16)               │
  └───────────────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────────────┐
  │  TimeoutError: payment-service did not respond            │
  │  test_checkout_flow  ·  Launch #129  ·  Feb 28            │
  │  Still open — no linked ticket                            │
  └───────────────────────────────────────────────────────────┘
```

---

### 4.2 UI Mockup — Similar Failures Sidebar

```
  Failed test detail                     │  Similar failures (5)
  ────────────────────────────────────── │ ────────────────────
  test_payment_gateway  #142             │  Score  Name
                                         │
  AssertionError: Expected 200, got 502  │  0.97   test_payment_retry
  payment.py : line 88                   │         Launch #138 · Fixed
                                         │         JIRA-4421
  [Mark defect]  [View raw log]          │
                                         │  0.91   test_refund_flow
                                         │         Launch #135 · Open
                                         │
                                         │  0.88   test_void_transaction
                                         │         Launch #131 · Fixed
                                         │         JIRA-4310
                                         │
                                         │  [ Search more like this → ]
```

---

### 4.3 Backend — FAISS Index

**File:** `search/index.py`

```python
import faiss
import numpy as np
import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
INDEX_PATH = Path("data/failures.faiss")
META_PATH  = Path("data/failures_meta.pkl")

def build_index(failures: list[dict]):
    """
    failures: list of { failure_id, exception_type, message, test_name, launch_id }
    Build flat L2 index — no quantisation needed for <1M failures.
    """
    texts = [f"{f['exception_type']}: {f['message']}" for f in failures]
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True)

    dim = embeddings.shape[1]             # 384 for MiniLM
    index = faiss.IndexFlatIP(dim)        # inner product = cosine sim (normalised vectors)
    index.add(embeddings.astype("float32"))

    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(failures, f)

def search(query: str, top_k: int = 5) -> list[dict]:
    index = faiss.read_index(str(INDEX_PATH))
    with open(META_PATH, "rb") as f:
        metadata = pickle.load(f)

    q_emb = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = index.search(q_emb, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        item = metadata[idx].copy()
        item["score"] = round(float(score), 3)
        results.append(item)
    return results
```

---

### 4.4 Backend — BM25 Hybrid Reranker

**File:** `search/hybrid.py`

```python
from rank_bm25 import BM25Okapi
from search.index import search as faiss_search

def tokenise(text: str) -> list[str]:
    return text.lower().split()

def hybrid_search(query: str, corpus: list[dict], top_k: int = 10) -> list[dict]:
    """
    1. Get top-20 from FAISS (semantic)
    2. Score all with BM25 (keyword)
    3. Merge with RRF (reciprocal rank fusion) — no weight tuning needed
    """
    semantic = faiss_search(query, top_k=20)
    sem_ids  = {r["failure_id"]: rank for rank, r in enumerate(semantic)}

    texts = [f"{c['exception_type']}: {c['message']}" for c in corpus]
    bm25  = BM25Okapi([tokenise(t) for t in texts])
    bm25_scores = bm25.get_scores(tokenise(query))
    bm25_ranked = sorted(range(len(corpus)), key=lambda i: -bm25_scores[i])
    bm25_ids = {corpus[i]["failure_id"]: rank for rank, i in enumerate(bm25_ranked[:20])}

    # Reciprocal Rank Fusion
    all_ids = set(sem_ids) | set(bm25_ids)
    k = 60  # RRF constant
    rrf_scores = {
        fid: (1 / (k + sem_ids.get(fid, 1000))) + (1 / (k + bm25_ids.get(fid, 1000)))
        for fid in all_ids
    }

    top_ids = sorted(rrf_scores, key=lambda x: -rrf_scores[x])[:top_k]
    id_to_item = {r["failure_id"]: r for r in semantic}
    id_to_item.update({corpus[i]["failure_id"]: corpus[i]
                       for i in range(len(corpus)) if corpus[i]["failure_id"] in top_ids})

    return [id_to_item[fid] for fid in top_ids if fid in id_to_item]
```

---

### 4.5 APIs — Phase 4

#### `GET /api/v2/search/failures`

**Query params:** `q=payment+service+timeout`, `project_id=checkout-service`, `limit=10`

**Response:**
```json
{
  "query": "payment service timeout",
  "total_hits": 23,
  "results": [
    {
      "failure_id": "f_4421",
      "test_name": "test_payment_gateway",
      "exception_type": "AssertionError",
      "message": "Expected 200, got 502",
      "launch_id": "138",
      "launched_at": "2025-03-15",
      "jira_ticket": "JIRA-4421",
      "resolved": true,
      "score": 0.97
    }
  ]
}
```

---

#### `GET /api/v2/failure/{failure_id}/similar`

Returns top-5 similar historical failures for the sidebar.

**Query params:** `top_k=5`

**Response:**
```json
{
  "failure_id": "f_8821",
  "similar": [
    {
      "failure_id": "f_4421",
      "test_name": "test_payment_retry",
      "score": 0.97,
      "launch_id": "138",
      "jira_ticket": "JIRA-4421",
      "resolved": true
    }
  ]
}
```

---

## ML Analyser Stack {#ml-analyser-stack}

### Model choices and rationale

| Component | Model / Library | Size | Why |
|-----------|----------------|------|-----|
| Embeddings | `all-MiniLM-L6-v2` | ~80 MB | Trained on short text pairs, 384-dim, CPU inference <10ms per log |
| Vector store | `FAISS IndexFlatIP` | ~5 MB + index | In-process, no external service, cosine sim on normalised vectors |
| Keyword search | `rank-bm25` | ~1 MB | Exact match on error codes and class names — complements semantic search |
| Clustering | `HDBSCAN` | ~3 MB | No k needed, handles noise points as "unclustered" |

### Index update strategy

- Index is rebuilt incrementally — new failures added on launch completion
- Full rebuild runs nightly (cron) to stay consistent with any DB corrections
- FAISS flat index rebuild for 100k failures takes ~8s on a 2-core CPU

### Dependency install

```bash
pip install sentence-transformers faiss-cpu hdbscan rank-bm25
# No GPU required. All models run on CPU.
# sentence-transformers will download all-MiniLM-L6-v2 on first run (~80MB).
```

---

## API Reference — Full Index {#api-reference}

| Method | Endpoint | Phase | Description |
|--------|----------|-------|-------------|
| GET | `/api/v2/launch/{id}/failures` | 1 | Parsed failure cards for a launch |
| GET | `/api/v2/launch/{id}/clusters` | 1 | Failure clusters for a launch |
| GET | `/api/v2/project/{id}/flakiness` | 2 | Flaky test list with trend |
| GET | `/api/v2/project/{id}/pass-rate` | 2 | Pass rate time series |
| GET | `/api/v2/project/{id}/duration-trends` | 2 | Test duration trend + flags |
| POST | `/api/v2/project/{id}/alerts` | 3 | Create alert rule |
| GET | `/api/v2/project/{id}/alerts` | 3 | List alert rules |
| DELETE | `/api/v2/project/{id}/alerts/{rule_id}` | 3 | Delete alert rule |
| POST | `/api/v2/dashboard/{id}/share` | 3 | Generate shareable link |
| DELETE | `/api/v2/dashboard/{id}/share/{token}` | 3 | Revoke share link |
| GET | `/share/{token}` | 3 | Public read-only dashboard |
| POST | `/api/v2/project/{id}/digest` | 3 | Create scheduled digest |
| GET | `/api/v2/search/failures` | 4 | Semantic + BM25 search |
| GET | `/api/v2/failure/{id}/similar` | 4 | Similar failures sidebar |

---

*All endpoints require Bearer token auth except `GET /share/{token}` which is public read-only.*
