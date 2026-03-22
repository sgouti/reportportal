# Phase 2 — Dashboard & Trend UI Specs

## 1. Flakiness dashboard

```
Flakiness Report  ·  Project: checkout-service
──────────────────────────────────────────────

  Period [ Last 30 days ▾ ]    Min flakiness % [ 5% ▾ ]

  ┌────────────────────────────────────────────────────────┐
  │  Project flakiness rate — last 30d                     │
  │                                                        │
  │  12% ┤                    *                            │
  │   8% ┤         *    *  *    *   *                      │
  │   4% ┤   *  *                        *   *            │
  │   0% ┼────────────────────────────────────────────    │
  │       Mar 1   Mar 7   Mar 14   Mar 21                 │
  └────────────────────────────────────────────────────────┘

  Top flaky tests                         [ Export CSV ]

  ┌──────────────────────────────┬────────┬───────┬───────┐
  │ Test name                    │ Flaky% │ Fails │ Trend │
  ├──────────────────────────────┼────────┼───────┼───────┤
  │ test_payment_retry           │  38%   │  8/21 │  ↑↑  │
  │ test_session_timeout         │  24%   │  5/21 │  →   │
  │ test_search_results_order    │  14%   │  3/21 │  ↓   │
  └──────────────────────────────┴────────┴───────┴───────┘
```

**Flakiness definition:** test has both PASSED and FAILED results within
the selected window, with no code change between runs.

---

## 2. Pass rate — time-range trend picker

```
Pass rate trend

  [ ← ]  Mar 2025  [ → ]   [ 7d | 30d | 90d | Custom ]

  ┌────────────────────────────────────────────────────────┐
  │  100% ┤                                               │
  │   90% ┤  ██████████████████████████████████████      │
  │   80% ┤                                        ██    │
  │   70% ┤                                              │
  │        Mar 1    Mar 7    Mar 14    Mar 21            │
  └────────────────────────────────────────────────────────┘

  Compare to previous period  [ ON / OFF ]
```

**Key change:** date range is a shared dashboard context.
Change once — all widgets update. No per-widget date pickers.

---

## 3. Test duration trend table

```
Slowest tests — duration trend (last 30d)

  ┌──────────────────────────────┬────────┬──────────┬──────┐
  │ Test name                    │  Avg   │ 30d ago  │  Δ   │
  ├──────────────────────────────┼────────┼──────────┼──────┤
  │ test_full_checkout_e2e       │ 14.2s  │   9.1s   │ +56% │ ← flagged
  │ test_report_pdf_export       │  8.8s  │   8.6s   │  +2% │
  │ test_user_bulk_import        │  6.1s  │   7.2s   │ -15% │
  └──────────────────────────────┴────────┴──────────┴──────┘

  ⚠ Tests with > 20% duration increase are flagged automatically
```

---

## API calls from this UI

| Action | Endpoint |
|---|---|
| Flakiness list | `GET /api/v2/project/{id}/flakiness?days=30&min_pct=5` |
| Pass rate series | `GET /api/v2/project/{id}/pass-rate?from=&to=&granularity=day` |
| Duration trends | `GET /api/v2/project/{id}/duration-trends?days=30&flag_pct_increase=20` |
