"""Score AnswerResponse against Scenario.expected from the matrix."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bfs_bot.demo_data.scenarios import Scenario
from bfs_bot.schemas import AnswerResponse


@dataclass
class ScoreResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def _trace_agents(response: AnswerResponse) -> set[str]:
    return {step.agent for step in response.trace}


def _answer_text(response: AnswerResponse) -> str:
    return response.answer.lower()


def score_scenario(scenario: Scenario, response: AnswerResponse) -> ScoreResult:
    """Return pass/fail and human-readable failure reasons."""
    expected = scenario.expected
    failures: list[str] = []

    if response.route != scenario.path:
        failures.append(f"route: got {response.route!r}, want {scenario.path!r}")

    if "escalate" in expected and response.escalate != expected["escalate"]:
        failures.append(
            f"escalate: got {response.escalate}, want {expected['escalate']}"
        )

    if expected.get("cite_policy") is True and not response.policy_citations:
        failures.append("cite_policy: expected policy citations, got none")
    if expected.get("cite_policy") is False and response.policy_citations:
        failures.append("cite_policy: expected no policy citations")

    if expected.get("cite_data") is True and not response.data_citations:
        failures.append("cite_data: expected data citations, got none")
    if expected.get("cite_data") is False and response.data_citations:
        failures.append("cite_data: expected no data citations")

    agents = _trace_agents(response)
    if expected.get("no_db") is True and "structured_data_agent" in agents:
        failures.append("no_db: structured_data_agent should not run")
    if expected.get("no_policy") is True and "policy_retrieval_agent" in agents:
        failures.append("no_policy: policy_retrieval_agent should not run")

    text = _answer_text(response)
    policy_versions = {c.version.lower() for c in response.policy_citations}

    if "membership_months" in expected:
        if str(expected["membership_months"]) not in response.answer:
            failures.append(
                f"membership_months: expected {expected['membership_months']} in answer"
            )

    if "months_required" in expected:
        if str(expected["months_required"]) not in response.answer:
            failures.append(
                f"months_required: expected {expected['months_required']} in answer"
            )

    if "eligible_from" in expected:
        if expected["eligible_from"] not in response.answer:
            failures.append(
                f"eligible_from: expected {expected['eligible_from']} in answer"
            )

    if code := expected.get("discount_code"):
        if str(code).lower() not in text and str(code) not in response.answer:
            failures.append(f"discount_code: expected {code!r} in answer")

    if pv := expected.get("policy_version"):
        pv_lower = str(pv).lower()
        if pv_lower not in text and pv_lower not in policy_versions:
            failures.append(f"policy_version: expected {pv!r} in answer or citations")

    if pct := expected.get("discount_percent"):
        if str(pct) not in response.answer and f"{pct}%" not in text:
            failures.append(f"discount_percent: expected {pct} in answer")

    if pct := expected.get("annual_discount_percent"):
        if str(pct) not in response.answer and f"{pct}%" not in text:
            failures.append(f"annual_discount_percent: expected {pct} in answer")

    if "days_after_due" in expected:
        if str(expected["days_after_due"]) not in response.answer:
            failures.append(
                f"days_after_due: expected {expected['days_after_due']} in answer"
            )

    if "grace_period_days" in expected:
        g = expected["grace_period_days"]
        if str(g) not in response.answer and f"{g}-day" not in text:
            failures.append(f"grace_period_days: expected {g} in answer")

    if paid := expected.get("paid_on"):
        if paid not in response.answer:
            failures.append(f"paid_on: expected {paid} in answer")

    if "days_before_demo" in expected:
        if str(expected["days_before_demo"]) not in response.answer:
            failures.append(
                f"days_before_demo: expected {expected['days_before_demo']} in answer"
            )

    if "refund_window_days" in expected:
        rw = expected["refund_window_days"]
        if str(rw) not in response.answer and f"{rw}-day" not in text:
            failures.append(f"refund_window_days: expected {rw} in answer")

    if demo := expected.get("demo_date"):
        if demo not in response.answer:
            failures.append(f"demo_date: expected {demo} in answer")

    if expected.get("no_db") is True and scenario.path == "policy_only":
        if "14" not in response.answer:
            failures.append("policy_only: expected refund window (14 days) in answer")

    if expected.get("no_policy") is True and scenario.path == "data_only":
        if not response.data_citations:
            failures.append("data_only: expected payment data citation")

    _score_summary_keywords(expected, text, failures)

    return ScoreResult(passed=len(failures) == 0, failures=failures)


def _score_summary_keywords(
    expected: dict[str, Any], text: str, failures: list[str]
) -> None:
    """Loose checks derived from brief summary phrases."""
    summary = str(expected.get("summary", "")).lower()
    if not summary:
        return

    if "billing error" in summary and "billing error" not in text and "escalat" not in text:
        failures.append("summary: expected billing-error / escalation language")

    if "loyalty10 applied correctly" in summary:
        if "loyalty10" not in text and "loyalty 10" not in text:
            failures.append("summary: expected LOYALTY10 applied narrative")
        if "v3" not in text:
            failures.append("summary: expected v3 reference")

    if "v2 was in force" in summary:
        if "v2" not in text:
            failures.append("summary: expected v2 versioning narrative")
        if "5" not in text and "loyalty5" not in text:
            failures.append("summary: expected 5% / LOYALTY5 reference")

    if "cannot be combined" in summary:
        if "cannot" not in text and "can't" not in text and "not be combined" not in text:
            failures.append("summary: expected non-stacking language")
        if "15" not in text and "annual" not in text:
            failures.append("summary: expected annual 15% applied")

    if "grace period" in summary:
        if "grace" not in text:
            failures.append("summary: expected grace-period language")

    if "outside the 14-day window" in summary:
        if "outside" not in text and "14" not in text:
            failures.append("summary: expected outside refund window language")

    if summary.strip() == "14 days.":
        if not re.search(r"\b14\b", text):
            failures.append("summary: expected 14-day refund window")
