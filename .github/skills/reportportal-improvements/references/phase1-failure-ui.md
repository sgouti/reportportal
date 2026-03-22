# Phase 1 — Failure Reporting UI Specs

## 1. Smart failure card

Replaces the raw log panel. Root failure line surfaced at the top.

```
┌─────────────────────────────────────────────────────────────────┐
│  FAILED  checkout_test.py::test_payment_gateway                 │
│  Duration: 1.2s  ·  Launch #142  ·  2025-03-21 09:14           │
├─────────────────────────────────────────────────────────────────┤
│  Failure summary                                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  AssertionError: Expected 200, got 502                    │  │
│  │  at checkout/payment.py : line 88   ← root line          │  │
│  │                                                           │  │
│  │  Expected    200                                          │  │
│  │  Actual      502                                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Similar failures (3)                           [ View all → ] │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────┐  │
│  │ test_refund #138 │ │ test_void   #135 │ │ test_auth #131 │  │
│  └──────────────────┘ └──────────────────┘ └────────────────┘  │
│                                                                 │
│  [ Product Bug ] [ Automation Bug ] [ System Issue ]           │
│  [ Link Jira ticket ]                  [ View raw log ↓ ]     │
└─────────────────────────────────────────────────────────────────┘
```

**UI rules:**
- Raw log collapsed by default — one click expands
- Expected/actual diff only shown when parseable from message
- Similar failures pulled from FAISS (Phase 4 back-compat: show empty if index not built yet)
- Defect type buttons directly update the test item status in DB

---

## 2. Failure cluster view (within a launch)

```
Launch #142  ·  87 tests  ·  61 passed  ·  26 failed
──────────────────────────────────────────────────────

  Failure clusters                         [ Sort: by count ▾ ]

  ┌──────────────────────────────────────────────────────────┐
  │  Cluster A  ·  14 tests                    [Expand ▾]   │
  │  AssertionError — payment.py line 88                     │
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │  Cluster B  ·  8 tests                     [Expand ▾]   │
  │  AssertionError — user_role fixture                      │
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │  Unclustered (novel)  ·  4 tests           [Expand ▾]   │
  │  No historical match — review manually                   │
  └──────────────────────────────────────────────────────────┘
```

**UI rules:**
- Clusters sorted by count descending by default
- Expand shows individual test items with link to failure card
- Unclustered (HDBSCAN label = -1) always shown last in red/amber

---

## React component outline

```
<FailureCard>
  <FailureHeader />          // test name, launch, duration
  <FailureSummaryBox>        // exception, root line, diff
    <ExpectedActualDiff />   // only rendered if parsed
  </FailureSummaryBox>
  <SimilarFailures />        // calls GET /failure/{id}/similar
  <DefectTypeButtons />      // calls PATCH /test-item/{id}/issue-type
  <RawLogCollapsible />
</FailureCard>

<ClusterView>
  <ClusterGroup v-for="cluster in clusters">
    <ClusterHeader />        // label, count
    <TestItemList />         // expanded: links to FailureCard
  </ClusterGroup>
</ClusterView>
```

---

## API calls from this UI

| Action | Endpoint |
|---|---|
| Load failure card | `GET /api/v2/launch/{id}/failures` |
| Load cluster view | `GET /api/v2/launch/{id}/clusters` |
| Load similar failures | `GET /api/v2/failure/{id}/similar` |
| Update defect type | `PATCH /api/v2/test-item/{id}/issue-type` |
