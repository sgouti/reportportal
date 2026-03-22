"""
flakiness.py — computes flakiness % and trend per test over a time window.

Usage:
    from flakiness import compute_flakiness
    report = compute_flakiness(project_id="checkout-service", days=30, min_pct=5)
"""

from collections import defaultdict
from datetime import datetime, timedelta


def compute_flakiness(
    project_id: str,
    days: int = 30,
    min_pct: float = 5.0,
    db_fetch_fn=None,   # injected in production; uses _mock_fetch for local tests
) -> list[dict]:
    """
    Returns list of flaky tests sorted by flakiness_pct descending.
    A test is flaky if it has both PASSED and FAILED within the window
    without a code change between runs.
    """
    fetch = db_fetch_fn or _mock_fetch
    since = datetime.utcnow() - timedelta(days=days)
    results = fetch(project_id, since=since)

    by_test: dict[str, list] = defaultdict(list)
    for r in results:
        by_test[r["test_id"]].append(r)

    flaky = []
    for test_id, runs in by_test.items():
        statuses = {r["status"] for r in runs}
        if "PASSED" not in statuses or "FAILED" not in statuses:
            continue  # not flaky

        total = len(runs)
        fails = sum(1 for r in runs if r["status"] == "FAILED")
        pct = round(fails / total * 100, 1)

        if pct < min_pct:
            continue

        flaky.append({
            "test_id": test_id,
            "test_name": runs[0]["name"],
            "flakiness_pct": pct,
            "failed_runs": fails,
            "total_runs": total,
            "trend": _trend(runs, days),
        })

    return sorted(flaky, key=lambda x: -x["flakiness_pct"])


def _trend(runs: list[dict], days: int) -> str:
    """Compares first half vs second half of the window."""
    mid = datetime.utcnow() - timedelta(days=days // 2)
    first  = [r for r in runs if r["launched_at"] < mid]
    second = [r for r in runs if r["launched_at"] >= mid]

    if not first or not second:
        return "stable"

    r1 = sum(1 for r in first  if r["status"] == "FAILED") / len(first)
    r2 = sum(1 for r in second if r["status"] == "FAILED") / len(second)

    if r2 > r1 + 0.05:
        return "worsening"
    if r2 < r1 - 0.05:
        return "improving"
    return "stable"


def _mock_fetch(project_id: str, since: datetime) -> list[dict]:
    """Fake data for local testing — replace with real DB call in production."""
    now = datetime.utcnow()
    return [
        {"test_id": "t1", "name": "test_payment_retry",   "status": "FAILED", "launched_at": now - timedelta(days=2)},
        {"test_id": "t1", "name": "test_payment_retry",   "status": "PASSED", "launched_at": now - timedelta(days=4)},
        {"test_id": "t1", "name": "test_payment_retry",   "status": "FAILED", "launched_at": now - timedelta(days=6)},
        {"test_id": "t2", "name": "test_session_timeout", "status": "PASSED", "launched_at": now - timedelta(days=1)},
        {"test_id": "t2", "name": "test_session_timeout", "status": "FAILED", "launched_at": now - timedelta(days=3)},
    ]


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    report = compute_flakiness("checkout-service", days=30, min_pct=0)
    for item in report:
        print(f"{item['test_name']}: {item['flakiness_pct']}%  trend={item['trend']}")
