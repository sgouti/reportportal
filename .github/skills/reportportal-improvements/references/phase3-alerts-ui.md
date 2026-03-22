# Phase 3 — Alerts & Stakeholder Sharing UI Specs

## 1. Alert rule builder

```
Alerts  ·  Project: checkout-service          [ + New rule ]
─────────────────────────────────────────────────────────────

  ┌──────────────────────────────────────────────────────────┐
  │  Rule: Pass rate drop                         [ Active ] │
  │                                                          │
  │  Condition:  Pass rate  [ < ▾ ]  [ 80 ]  %              │
  │  Window:     [ Any launch ▾ ]                            │
  │  Notify via: [ Slack ▾ ]   #qa-alerts                    │
  │              [ Email ▾ ]   team@company.com              │
  │                                                  [ Save ]│
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │  Rule: Novel failure cluster                  [ Active ] │
  │                                                          │
  │  Condition:  Novel cluster detected in launch            │
  │  Notify via: [ Slack ▾ ]   #qa-alerts                    │
  │                                                  [ Save ]│
  └──────────────────────────────────────────────────────────┘
```

**Supported conditions:**
- Pass rate below threshold
- Novel failure cluster detected (HDBSCAN unclustered count > 0)
- Flakiness % above threshold

**Supported channels:** Slack webhook, email, Microsoft Teams webhook

---

## 2. Scheduled digest config

```
Scheduled reports  ·  Project: checkout-service

  ┌──────────────────────────────────────────────────────────┐
  │  Daily summary digest                                    │
  │                                                          │
  │  Schedule:    [ Daily ▾ ]   at  [ 08:00 ▾ ]             │
  │  Recipients:  team@company.com, pm@company.com           │
  │  Include:     [x] Pass rate     [x] Flaky tests          │
  │               [x] New failures  [ ] Duration trends      │
  │                                                  [ Save ]│
  └──────────────────────────────────────────────────────────┘
```

**Digest email layout:**
```
Subject: [ReportPortal] checkout-service — Daily QA digest — Mar 21

  Pass rate:    91.2%  (↓ 2.1% from yesterday)
  Flaky tests:  3 active
  New failures: 2 novel clusters detected

  Top failures:
  - AssertionError: Expected 200, got 502 (14 tests)
  - TimeoutError: session expired (8 tests)

  [ View full dashboard → ]
```

---

## 3. Shareable read-only dashboard link

```
Share dashboard

  ┌──────────────────────────────────────────────────────────┐
  │  Read-only public link                                   │
  │                                                          │
  │  https://reportportal.io/share/abc123xyz      [ Copy ]  │
  │                                                          │
  │  Expires:   [ Never ▾ ]                                  │
  │  Scope:     [ This dashboard only ▾ ]                    │
  │                                                          │
  │  [ Revoke link ]                                         │
  └──────────────────────────────────────────────────────────┘
```

**Token rules:**
- 16-byte URL-safe random token (`secrets.token_urlsafe(16)`)
- Stored in DB with `dashboard_id`, `created_by`, `expires_at`, `revoked`
- Public endpoint `GET /share/{token}` — no auth, read-only response only

---

## API calls from this UI

| Action | Endpoint |
|---|---|
| Create alert rule | `POST /api/v2/project/{id}/alerts` |
| List alert rules | `GET /api/v2/project/{id}/alerts` |
| Delete alert rule | `DELETE /api/v2/project/{id}/alerts/{rule_id}` |
| Generate share link | `POST /api/v2/dashboard/{id}/share` |
| Revoke share link | `DELETE /api/v2/dashboard/{id}/share/{token}` |
| Public dashboard view | `GET /share/{token}` (no auth) |
| Create digest schedule | `POST /api/v2/project/{id}/digest` |
