"""
main.py — FastAPI entry point wiring all ReportPortal improvement endpoints.

Run locally:
    uvicorn main:app --reload --port 8000

Or via Docker:
    docker compose -f scripts/docker/docker-compose.dev.yml up
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from log_parser import parse as parse_log
from clusterer import build_clusters
from flakiness import compute_flakiness
from alert_engine import AlertRule, Condition, evaluate_on_launch_complete
from search_index import build_index, search as faiss_search, add_failure
from hybrid_search import hybrid_search

import secrets
import os


# ── App setup ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ReportPortal improvement API starting up...")
    yield
    print("Shutting down.")

app = FastAPI(
    title="ReportPortal Improvements API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory stores (replace with DB in production) ─────────────────────────

_failures_store: dict[str, dict] = {}        # failure_id → failure dict
_launches_store: dict[str, list] = {}        # launch_id  → [failure_id, ...]
_alert_rules:    dict[str, list] = {}        # project_id → [AlertRule, ...]
_share_tokens:   dict[str, dict] = {}        # token      → {dashboard_id, expires_at}
_digest_config:  dict[str, dict] = {}        # project_id → config


# ── Pydantic models ───────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    condition: Condition
    threshold: float | None = None
    channels: list[dict]

class ShareCreate(BaseModel):
    expires_days: int | None = None

class DigestCreate(BaseModel):
    schedule: str           # "daily" | "weekly"
    time: str               # "08:00"
    recipients: list[str]
    include: list[str]      # ["pass_rate", "flaky_tests", "new_failures"]

class IssueTypeUpdate(BaseModel):
    issue_type: str         # product_bug | automation_bug | system_issue | to_investigate


# ── Phase 1 — Failure reporting ───────────────────────────────────────────────

@app.get("/api/v2/launch/{launch_id}/failures")
def get_launch_failures(launch_id: str):
    """Parsed failure cards for all failed tests in a launch."""
    failure_ids = _launches_store.get(launch_id, [])
    failures = [_failures_store[fid] for fid in failure_ids if fid in _failures_store]
    if not failures:
        raise HTTPException(404, f"No failures found for launch {launch_id}")
    return {
        "launch_id": launch_id,
        "total_failed": len(failures),
        "failures": failures,
    }


@app.get("/api/v2/launch/{launch_id}/clusters")
def get_launch_clusters(launch_id: str):
    """Failure clusters grouped by HDBSCAN for a launch."""
    failure_ids = _launches_store.get(launch_id, [])
    failures = [_failures_store[fid] for fid in failure_ids if fid in _failures_store]
    if not failures:
        raise HTTPException(404, f"No failures for launch {launch_id}")
    clusters = build_clusters(failures)
    return {"launch_id": launch_id, "clusters": clusters}


@app.post("/api/v2/launch/{launch_id}/ingest")
def ingest_launch(launch_id: str, payload: dict):
    """
    Ingest raw test results for a launch.
    Parses logs, stores failures, updates FAISS index, fires alerts.

    payload: { project_id, tests: [{test_id, name, status, raw_log}] }
    """
    project_id   = payload["project_id"]
    failed_tests = [t for t in payload["tests"] if t["status"] == "FAILED"]

    parsed_failures = []
    for t in failed_tests:
        p = parse_log(t.get("raw_log", ""))
        failure = {
            "failure_id":      f"f_{t['test_id']}",
            "test_id":         t["test_id"],
            "test_name":       t["name"],
            "exception_type":  p.exception_type,
            "message":         p.message,
            "root_file":       p.root_file,
            "root_line":       p.root_line,
            "expected":        p.expected,
            "actual":          p.actual,
            "launch_id":       launch_id,
            "cluster_id":      None,
            "similar_count":   0,
            "issue_type":      "to_investigate",
        }
        _failures_store[failure["failure_id"]] = failure
        parsed_failures.append(failure)

    _launches_store[launch_id] = [f["failure_id"] for f in parsed_failures]

    # Update FAISS index incrementally
    for f in parsed_failures:
        add_failure(f)

    # Fire alert rules
    total   = len(payload["tests"])
    passed  = total - len(failed_tests)
    clusters = build_clusters(parsed_failures)
    novel_count = sum(1 for c in clusters if c["is_novel"])

    evaluate_on_launch_complete({
        "project_id":          project_id,
        "launch_id":           launch_id,
        "passed":              passed,
        "total":               total,
        "novel_cluster_count": novel_count,
        "flakiness_pct":       0,  # Phase 2 will compute this
    }, rules=_alert_rules.get(project_id, []))

    return {"ingested": len(parsed_failures), "clusters": len(clusters)}


@app.patch("/api/v2/test-item/{test_id}/issue-type")
def update_issue_type(test_id: str, body: IssueTypeUpdate):
    """Update defect categorisation for a test item."""
    fid = f"f_{test_id}"
    if fid not in _failures_store:
        raise HTTPException(404, f"Test item {test_id} not found")
    _failures_store[fid]["issue_type"] = body.issue_type
    return {"updated": True}


# ── Phase 2 — Dashboard & trends ─────────────────────────────────────────────

@app.get("/api/v2/project/{project_id}/flakiness")
def get_flakiness(
    project_id: str,
    days: int   = Query(30),
    min_pct: float = Query(5.0),
):
    """Flaky test list with trend for the project."""
    report = compute_flakiness(project_id, days=days, min_pct=min_pct)
    return {
        "period_days":          days,
        "flaky_test_count":     len(report),
        "project_flakiness_pct": round(sum(t["flakiness_pct"] for t in report) / max(len(report), 1), 1),
        "tests": report,
    }


@app.get("/api/v2/project/{project_id}/pass-rate")
def get_pass_rate(
    project_id: str,
    from_date: str = Query(alias="from"),
    to_date:   str = Query(alias="to"),
    granularity: str = Query("day"),
):
    """Pass rate time series between two dates."""
    # Stub — replace with real DB aggregation query
    return {
        "from": from_date,
        "to":   to_date,
        "granularity": granularity,
        "series": [
            {"date": from_date, "pass_rate": 91.2, "total": 320, "passed": 292}
        ],
    }


@app.get("/api/v2/project/{project_id}/duration-trends")
def get_duration_trends(
    project_id: str,
    days: int = Query(30),
    flag_pct_increase: float = Query(20.0),
):
    """Test duration trend table with flags for regressions."""
    # Stub — replace with real DB aggregation
    return {
        "tests": [
            {
                "test_id": "t_9001",
                "test_name": "test_full_checkout_e2e",
                "avg_duration_ms": 14200,
                "prev_avg_duration_ms": 9100,
                "delta_pct": 56.0,
                "flagged": True,
            }
        ]
    }


# ── Phase 3 — Alerts & sharing ────────────────────────────────────────────────

@app.post("/api/v2/project/{project_id}/alerts", status_code=201)
def create_alert(project_id: str, body: AlertCreate):
    rule = AlertRule(
        rule_id=f"r_{secrets.token_hex(4)}",
        project_id=project_id,
        condition=body.condition,
        threshold=body.threshold,
        channels=body.channels,
        active=True,
    )
    _alert_rules.setdefault(project_id, []).append(rule)
    return {"rule_id": rule.rule_id}


@app.get("/api/v2/project/{project_id}/alerts")
def list_alerts(project_id: str):
    rules = _alert_rules.get(project_id, [])
    return {"rules": [vars(r) for r in rules]}


@app.delete("/api/v2/project/{project_id}/alerts/{rule_id}", status_code=204)
def delete_alert(project_id: str, rule_id: str):
    rules = _alert_rules.get(project_id, [])
    _alert_rules[project_id] = [r for r in rules if r.rule_id != rule_id]


@app.post("/api/v2/dashboard/{dashboard_id}/share", status_code=201)
def create_share_link(dashboard_id: str, body: ShareCreate):
    token      = secrets.token_urlsafe(16)
    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(days=body.expires_days)).isoformat()
    _share_tokens[token] = {"dashboard_id": dashboard_id, "expires_at": expires_at, "revoked": False}
    return {
        "share_url":  f"https://reportportal.io/share/{token}",
        "expires_at": expires_at,
    }


@app.delete("/api/v2/dashboard/{dashboard_id}/share/{token}", status_code=204)
def revoke_share_link(dashboard_id: str, token: str):
    if token in _share_tokens:
        _share_tokens[token]["revoked"] = True


@app.get("/share/{token}")
def public_dashboard(token: str):
    """Public read-only endpoint — no auth required."""
    record = _share_tokens.get(token)
    if not record or record["revoked"]:
        raise HTTPException(404, "Link not found or revoked")
    if record["expires_at"] and datetime.utcnow().isoformat() > record["expires_at"]:
        raise HTTPException(410, "Link expired")
    return {"dashboard_id": record["dashboard_id"], "read_only": True}


@app.post("/api/v2/project/{project_id}/digest", status_code=201)
def create_digest(project_id: str, body: DigestCreate):
    _digest_config[project_id] = body.model_dump()
    return {"scheduled": True}


# ── Phase 4 — Semantic search ─────────────────────────────────────────────────

@app.get("/api/v2/search/failures")
def search_failures(
    q:          str = Query(..., description="Search query"),
    project_id: str | None = Query(None),
    limit:      int = Query(10),
):
    """BM25 + FAISS hybrid search over all historical failures."""
    corpus = list(_failures_store.values())
    if project_id:
        corpus = [f for f in corpus if f.get("project_id") == project_id]

    if not corpus:
        return {"query": q, "total_hits": 0, "results": []}

    try:
        results = hybrid_search(q, corpus=corpus, top_k=limit)
    except FileNotFoundError:
        # Index not yet built — fall back to BM25-only
        results = []

    return {"query": q, "total_hits": len(results), "results": results}


@app.get("/api/v2/failure/{failure_id}/similar")
def get_similar_failures(failure_id: str, top_k: int = Query(5)):
    """Top-k most similar historical failures for the sidebar."""
    failure = _failures_store.get(failure_id)
    if not failure:
        raise HTTPException(404, f"Failure {failure_id} not found")

    query   = f"{failure['exception_type']}: {failure['message']}"
    try:
        hits = faiss_search(query, top_k=top_k + 1)   # +1 to exclude self
    except FileNotFoundError:
        return {"failure_id": failure_id, "similar": []}

    similar = [h for h in hits if h.get("failure_id") != failure_id][:top_k]
    return {"failure_id": failure_id, "similar": similar}


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
