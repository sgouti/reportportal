"""
alert_engine.py — evaluates alert rules on launch completion and dispatches notifications.

Usage:
    from alert_engine import evaluate_on_launch_complete
    evaluate_on_launch_complete(launch_result)
"""

from dataclasses import dataclass
from enum import Enum
import requests   # for Slack/Teams webhooks


class Condition(str, Enum):
    PASS_RATE_BELOW        = "pass_rate_below"
    NOVEL_CLUSTER_DETECTED = "novel_cluster_detected"
    FLAKINESS_ABOVE        = "flakiness_above"


@dataclass
class AlertRule:
    rule_id:    str
    project_id: str
    condition:  Condition
    threshold:  float | None
    channels:   list[dict]   # [{"type": "slack"|"email"|"teams", "target": "..."}]
    active:     bool


def evaluate_on_launch_complete(launch_result: dict, rules: list[AlertRule] = None):
    """
    Called by event hook when a launch finishes.

    launch_result keys expected:
        project_id, launch_id, passed, total,
        novel_cluster_count, flakiness_pct
    """
    if rules is None:
        rules = _load_rules(launch_result["project_id"])

    for rule in rules:
        if not rule.active:
            continue
        fired, context = _check(rule, launch_result)
        if fired:
            _dispatch(rule, context, launch_result)


def _check(rule: AlertRule, launch: dict) -> tuple[bool, dict]:
    if rule.condition == Condition.PASS_RATE_BELOW:
        total = launch.get("total", 1)
        rate  = launch.get("passed", 0) / total * 100
        if rate < (rule.threshold or 80):
            return True, {"pass_rate": round(rate, 1), "threshold": rule.threshold}

    if rule.condition == Condition.NOVEL_CLUSTER_DETECTED:
        count = launch.get("novel_cluster_count", 0)
        if count > 0:
            return True, {"novel_clusters": count}

    if rule.condition == Condition.FLAKINESS_ABOVE:
        pct = launch.get("flakiness_pct", 0)
        if pct > (rule.threshold or 20):
            return True, {"flakiness_pct": pct}

    return False, {}


def _dispatch(rule: AlertRule, context: dict, launch: dict):
    message = _format(rule, context, launch)
    for ch in rule.channels:
        if ch["type"] == "slack":
            _send_slack(ch["target"], message)
        elif ch["type"] == "teams":
            _send_teams(ch["target"], message)
        elif ch["type"] == "email":
            _send_email(ch["target"], message)


def _format(rule: AlertRule, context: dict, launch: dict) -> str:
    base = f"[ReportPortal] Project: {launch['project_id']}  Launch: #{launch['launch_id']}\n"
    if rule.condition == Condition.PASS_RATE_BELOW:
        return base + f"Pass rate dropped to {context['pass_rate']}% (threshold: {context['threshold']}%)"
    if rule.condition == Condition.NOVEL_CLUSTER_DETECTED:
        return base + f"{context['novel_clusters']} new failure pattern(s) detected — review needed."
    if rule.condition == Condition.FLAKINESS_ABOVE:
        return base + f"Flakiness reached {context['flakiness_pct']}% this launch."
    return base + "Alert triggered."


def _send_slack(webhook_url: str, message: str):
    requests.post(webhook_url, json={"text": message}, timeout=5)


def _send_teams(webhook_url: str, message: str):
    requests.post(webhook_url, json={"text": message}, timeout=5)


def _send_email(address: str, message: str):
    # Wire to your SMTP/SES client here
    print(f"[email → {address}]: {message}")


def _load_rules(project_id: str) -> list[AlertRule]:
    """Replace with real DB fetch in production."""
    return [
        AlertRule(
            rule_id="r_001", project_id=project_id,
            condition=Condition.PASS_RATE_BELOW, threshold=80.0,
            channels=[{"type": "email", "target": "team@company.com"}],
            active=True,
        )
    ]


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    evaluate_on_launch_complete({
        "project_id": "checkout-service",
        "launch_id": "142",
        "passed": 61,
        "total": 87,
        "novel_cluster_count": 2,
        "flakiness_pct": 12.0,
    })
