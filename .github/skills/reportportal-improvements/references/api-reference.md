# API Reference

All endpoints require `Authorization: Bearer <token>` except `GET /share/{token}`.
Base URL: `https://your-rp-instance/api/v2`

---

## Phase 1 — Failure reporting

### GET /launch/{launch_id}/failures
Parsed failure cards for all failed tests in a launch.

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

### GET /launch/{launch_id}/clusters
Failure clusters grouped by HDBSCAN.

```json
{
  "launch_id": "142",
  "clusters": [
    { "cluster_id": 0, "label": "AssertionError — payment.py", "count": 14, "is_novel": false, "members": ["t_8821"] },
    { "cluster_id": -1, "label": "Unclustered (novel)", "count": 4, "is_novel": true, "members": ["t_8900"] }
  ]
}
```

### PATCH /test-item/{test_id}/issue-type
Update defect categorisation.

**Request:** `{ "issue_type": "product_bug" | "automation_bug" | "system_issue" | "to_investigate" }`
**Response:** `200 OK`

---

## Phase 2 — Dashboard & trends

### GET /project/{project_id}/flakiness
Query params: `days=30`, `min_pct=5`, `page=1`, `limit=50`

```json
{
  "period_days": 30,
  "flaky_test_count": 12,
  "project_flakiness_pct": 8.4,
  "tests": [
    { "test_id": "t_8821", "test_name": "test_payment_retry", "flakiness_pct": 38.1, "failed_runs": 8, "total_runs": 21, "trend": "worsening" }
  ]
}
```

### GET /project/{project_id}/pass-rate
Query params: `from=2025-03-01`, `to=2025-03-21`, `granularity=day|week`

```json
{
  "series": [
    { "date": "2025-03-01", "pass_rate": 91.2, "total": 320, "passed": 292 }
  ]
}
```

### GET /project/{project_id}/duration-trends
Query params: `days=30`, `flag_pct_increase=20`

```json
{
  "tests": [
    { "test_id": "t_9001", "test_name": "test_full_checkout_e2e", "avg_duration_ms": 14200, "prev_avg_duration_ms": 9100, "delta_pct": 56.0, "flagged": true }
  ]
}
```

---

## Phase 3 — Alerts & sharing

### POST /project/{project_id}/alerts
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
**Response:** `201 Created` `{ "rule_id": "r_001" }`

### GET /project/{project_id}/alerts
Returns list of all rules for the project.

### DELETE /project/{project_id}/alerts/{rule_id}
**Response:** `204 No Content`

### POST /dashboard/{dashboard_id}/share
```json
{ "expires_days": null }
```
**Response:** `{ "share_url": "https://reportportal.io/share/abc123xyz", "expires_at": null }`

### DELETE /dashboard/{dashboard_id}/share/{token}
Revokes the token. **Response:** `204 No Content`

### GET /share/{token}  ← no auth required
Returns read-only dashboard payload with `"read_only": true`.

### POST /project/{project_id}/digest
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

## Phase 4 — Semantic search

### GET /search/failures
Query params: `q=payment+timeout`, `project_id=` (optional), `limit=10`

```json
{
  "query": "payment service timeout",
  "total_hits": 23,
  "results": [
    { "failure_id": "f_4421", "test_name": "test_payment_gateway", "exception_type": "AssertionError", "message": "Expected 200, got 502", "launch_id": "138", "jira_ticket": "JIRA-4421", "resolved": true, "score": 0.97 }
  ]
}
```

### GET /failure/{failure_id}/similar
Query params: `top_k=5`

```json
{
  "failure_id": "f_8821",
  "similar": [
    { "failure_id": "f_4421", "test_name": "test_payment_retry", "score": 0.97, "launch_id": "138", "jira_ticket": "JIRA-4421", "resolved": true }
  ]
}
```

---

## Full endpoint index

| Method | Endpoint | Phase |
|---|---|---|
| GET | `/launch/{id}/failures` | 1 |
| GET | `/launch/{id}/clusters` | 1 |
| PATCH | `/test-item/{id}/issue-type` | 1 |
| GET | `/project/{id}/flakiness` | 2 |
| GET | `/project/{id}/pass-rate` | 2 |
| GET | `/project/{id}/duration-trends` | 2 |
| POST | `/project/{id}/alerts` | 3 |
| GET | `/project/{id}/alerts` | 3 |
| DELETE | `/project/{id}/alerts/{rule_id}` | 3 |
| POST | `/dashboard/{id}/share` | 3 |
| DELETE | `/dashboard/{id}/share/{token}` | 3 |
| GET | `/share/{token}` (public) | 3 |
| POST | `/project/{id}/digest` | 3 |
| GET | `/search/failures` | 4 |
| GET | `/failure/{id}/similar` | 4 |
