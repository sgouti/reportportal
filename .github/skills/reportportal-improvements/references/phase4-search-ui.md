# Phase 4 — Semantic Failure Search UI Specs

## 1. Search bar

```
Search failures  ·  All projects ▾

  ┌───────────────────────────────────────────────────────────────┐
  │  payment service timeout                           [ Search ] │
  └───────────────────────────────────────────────────────────────┘

  23 results  ·  ranked by relevance

  ┌─────────────────────────────────────────────────────────────┐
  │  AssertionError: connection timeout after 30s               │
  │  test_payment_gateway  ·  Launch #138  ·  Mar 15            │
  │  Fixed → JIRA-4421  (by @ravi, Mar 16)                      │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  TimeoutError: payment-service did not respond              │
  │  test_checkout_flow  ·  Launch #129  ·  Feb 28              │
  │  Still open — no linked ticket                              │
  └─────────────────────────────────────────────────────────────┘
```

**Search behaviour:**
- BM25 + FAISS hybrid — handles both exact class name match and semantic match
- Results show Jira ticket if linked, or "Still open" if not
- Cross-project search by default; project filter available

---

## 2. Similar failures sidebar (on failure card)

```
  Failed test detail                    │  Similar failures (5)
  ───────────────────────────────────── │ ─────────────────────
  test_payment_gateway  #142            │  Score  Test
                                        │
  AssertionError: Expected 200, got 502 │  0.97  test_payment_retry
  payment.py : line 88                  │        Launch #138  ·  Fixed
                                        │        JIRA-4421
  [Mark defect]  [View raw log]         │
                                        │  0.91  test_refund_flow
                                        │        Launch #135  ·  Open
                                        │
                                        │  0.88  test_void_transaction
                                        │        Launch #131  ·  Fixed
                                        │        JIRA-4310
                                        │
                                        │  [ Search more like this → ]
```

**Sidebar rules:**
- Top-5 by RRF score, rendered on failure card open
- "Fixed" = has linked Jira ticket marked resolved
- "Open" = no ticket or ticket still open
- "Search more like this" fires the search bar pre-filled with exception + message

---

## Index update strategy

- New failures indexed on launch completion (event hook)
- Full FAISS rebuild runs nightly (cron) for consistency
- Rebuild for 100k failures ≈ 8s on 2-core CPU

---

## API calls from this UI

| Action | Endpoint |
|---|---|
| Search failures | `GET /api/v2/search/failures?q=payment+timeout&project_id=...` |
| Similar failures sidebar | `GET /api/v2/failure/{id}/similar?top_k=5` |
