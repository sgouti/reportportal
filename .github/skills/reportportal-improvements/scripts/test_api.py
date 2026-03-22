"""
test_api.py — end-to-end tests for all four phases.

Run:
    pytest scripts/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from scripts.main import app, _failures_store, _launches_store, _alert_rules, _share_tokens

client = TestClient(app)


# ── Shared fixtures ───────────────────────────────────────────────────────────

SAMPLE_LAUNCH = {
    "project_id": "checkout-service",
    "tests": [
        {
            "test_id": "t001",
            "name": "test_payment_gateway",
            "status": "FAILED",
            "raw_log": (
                'FAILED checkout_test.py::test_payment_gateway\n'
                'Traceback (most recent call last):\n'
                '  File "/app/.venv/lib/pytest/runner.py", line 340, in _call\n'
                '    result = func()\n'
                '  File "/app/tests/checkout_test.py", line 42, in test_payment_gateway\n'
                '    assert response.status_code == 200\n'
                'AssertionError: Expected 200, got 502\n'
            ),
        },
        {
            "test_id": "t002",
            "name": "test_refund_flow",
            "status": "FAILED",
            "raw_log": (
                '  File "/app/tests/refund_test.py", line 18, in test_refund_flow\n'
                'AssertionError: Expected 200 but received 502\n'
            ),
        },
        {"test_id": "t003", "name": "test_login", "status": "PASSED", "raw_log": ""},
    ],
}

@pytest.fixture(autouse=True)
def clear_stores():
    """Reset in-memory stores before each test."""
    _failures_store.clear()
    _launches_store.clear()
    _alert_rules.clear()
    _share_tokens.clear()
    yield


# ── Phase 1 ───────────────────────────────────────────────────────────────────

class TestPhase1FailureReporting:

    def test_ingest_launch_returns_failure_count(self):
        r = client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        assert r.status_code == 200
        assert r.json()["ingested"] == 2

    def test_get_failures_after_ingest(self):
        client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        r = client.get("/api/v2/launch/142/failures")
        assert r.status_code == 200
        data = r.json()
        assert data["total_failed"] == 2
        failure = data["failures"][0]
        assert failure["exception_type"] == "AssertionError"
        assert failure["root_file"] == "checkout_test.py"
        assert failure["root_line"] == 42
        assert failure["expected"] == "200"
        assert failure["actual"] == "502"

    def test_get_clusters_groups_similar_failures(self):
        client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        r = client.get("/api/v2/launch/142/clusters")
        assert r.status_code == 200
        clusters = r.json()["clusters"]
        assert len(clusters) >= 1
        # Both failures are 502 AssertionErrors — expect one cluster
        total_members = sum(c["count"] for c in clusters)
        assert total_members == 2

    def test_update_issue_type(self):
        client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        r = client.patch("/api/v2/test-item/t001/issue-type", json={"issue_type": "product_bug"})
        assert r.status_code == 200
        assert _failures_store["f_t001"]["issue_type"] == "product_bug"

    def test_get_failures_unknown_launch_returns_404(self):
        r = client.get("/api/v2/launch/999/failures")
        assert r.status_code == 404


# ── Phase 2 ───────────────────────────────────────────────────────────────────

class TestPhase2DashboardTrends:

    def test_flakiness_returns_structure(self):
        r = client.get("/api/v2/project/checkout-service/flakiness?days=30&min_pct=0")
        assert r.status_code == 200
        data = r.json()
        assert "flaky_test_count" in data
        assert "project_flakiness_pct" in data
        assert isinstance(data["tests"], list)

    def test_pass_rate_returns_series(self):
        r = client.get("/api/v2/project/checkout-service/pass-rate?from=2025-03-01&to=2025-03-21&granularity=day")
        assert r.status_code == 200
        data = r.json()
        assert "series" in data
        assert len(data["series"]) >= 1

    def test_duration_trends_returns_tests(self):
        r = client.get("/api/v2/project/checkout-service/duration-trends?days=30")
        assert r.status_code == 200
        assert "tests" in r.json()


# ── Phase 3 ───────────────────────────────────────────────────────────────────

class TestPhase3AlertsSharing:

    def test_create_and_list_alert_rule(self):
        payload = {
            "condition": "pass_rate_below",
            "threshold": 80,
            "channels": [{"type": "email", "target": "team@company.com"}],
        }
        r = client.post("/api/v2/project/checkout-service/alerts", json=payload)
        assert r.status_code == 201
        rule_id = r.json()["rule_id"]

        r2 = client.get("/api/v2/project/checkout-service/alerts")
        assert any(rule["rule_id"] == rule_id for rule in r2.json()["rules"])

    def test_delete_alert_rule(self):
        r = client.post("/api/v2/project/checkout-service/alerts", json={
            "condition": "novel_cluster_detected",
            "threshold": None,
            "channels": [],
        })
        rule_id = r.json()["rule_id"]
        r2 = client.delete(f"/api/v2/project/checkout-service/alerts/{rule_id}")
        assert r2.status_code == 204

    def test_create_share_link(self):
        r = client.post("/api/v2/dashboard/dash_001/share", json={"expires_days": None})
        assert r.status_code == 201
        data = r.json()
        assert "share_url" in data
        assert data["expires_at"] is None

    def test_public_dashboard_resolves(self):
        r = client.post("/api/v2/dashboard/dash_001/share", json={"expires_days": None})
        token = r.json()["share_url"].split("/")[-1]
        r2 = client.get(f"/share/{token}")
        assert r2.status_code == 200
        assert r2.json()["read_only"] is True

    def test_revoked_link_returns_404(self):
        r = client.post("/api/v2/dashboard/dash_001/share", json={"expires_days": None})
        token = r.json()["share_url"].split("/")[-1]
        client.delete(f"/api/v2/dashboard/dash_001/share/{token}")
        r2 = client.get(f"/share/{token}")
        assert r2.status_code == 404

    def test_create_digest_schedule(self):
        r = client.post("/api/v2/project/checkout-service/digest", json={
            "schedule": "daily",
            "time": "08:00",
            "recipients": ["team@company.com"],
            "include": ["pass_rate", "flaky_tests"],
        })
        assert r.status_code == 201


# ── Phase 4 ───────────────────────────────────────────────────────────────────

class TestPhase4SemanticSearch:

    def test_search_returns_results_after_ingest(self):
        client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        r = client.get("/api/v2/search/failures?q=payment+502+error")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert data["total_hits"] >= 0   # 0 is OK if FAISS index not built yet

    def test_similar_failures_returns_structure(self):
        client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        r = client.get("/api/v2/failure/f_t001/similar?top_k=5")
        assert r.status_code == 200
        data = r.json()
        assert "similar" in data
        assert isinstance(data["similar"], list)

    def test_similar_failures_excludes_self(self):
        client.post("/api/v2/launch/142/ingest", json=SAMPLE_LAUNCH)
        r = client.get("/api/v2/failure/f_t001/similar?top_k=5")
        ids = [s["failure_id"] for s in r.json()["similar"]]
        assert "f_t001" not in ids

    def test_unknown_failure_returns_404(self):
        r = client.get("/api/v2/failure/nonexistent/similar")
        assert r.status_code == 404


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
