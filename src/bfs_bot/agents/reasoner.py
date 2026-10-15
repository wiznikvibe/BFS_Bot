from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from bfs_bot.agents.policy import PolicyPassage
from bfs_bot.schemas import AgentStep, DataCitation, PolicyCitation

_MONTHS_REQUIRED_RE = re.compile(
    r"(\d+)\s*\)?\s*full months",
    re.I,
)


@dataclass(frozen=True)
class LoyaltyCompareResult:
    answer: str
    membership_months: int
    months_required: int
    eligible_from: date
    escalate: bool
    confidence: float
    data_citations: list[DataCitation]
    policy_citations: list[PolicyCitation]
    trace: list[AgentStep]


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start.day, last_day)
    return date(year, month, day)


def _parse_months_required(passages: list[PolicyPassage]) -> int | None:
    loyalty = [p for p in passages if p.doc_id == "loyalty-discount-policy"]
    for passage in loyalty:
        match = _MONTHS_REQUIRED_RE.search(passage.text)
        if match:
            return int(match.group(1))
    return None


def _loyalty_policy_passages(passages: list[PolicyPassage]) -> list[PolicyPassage]:
    return [p for p in passages if p.doc_id == "loyalty-discount-policy"]


def compare_loyalty_eligibility(
    *,
    customer: dict[str, Any],
    invoice: dict[str, Any] | None,
    policy_passages: list[PolicyPassage],
    as_of: date,
) -> LoyaltyCompareResult:
    """Criterion-by-criterion loyalty check (C001 and similar hybrid cases)."""
    trace: list[AgentStep] = []
    signup_raw = customer.get("signup_date")
    if isinstance(signup_raw, str):
        signup = date.fromisoformat(signup_raw)
    else:
        signup = signup_raw

    membership_months = _months_between(signup, as_of)
    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"Membership tenure: {membership_months} full month(s) "
                f"from signup {signup.isoformat()} to as_of {as_of.isoformat()}."
            ),
        )
    )

    loyalty_passages = _loyalty_policy_passages(policy_passages)
    months_required = _parse_months_required(loyalty_passages) or 12
    policy_version = loyalty_passages[0].version if loyalty_passages else "v3"
    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"Policy requirement (Loyalty {policy_version}): "
                f"{months_required} full month(s) of paid membership."
            ),
        )
    )

    eligible_from = _add_months(signup, months_required)
    meets_tenure = membership_months >= months_required
    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed" if meets_tenure else "not_met",
            detail=(
                f"Tenure criterion {'met' if meets_tenure else 'not met'}; "
                f"eligible from {eligible_from.isoformat()}."
            ),
        )
    )

    discount_amt = Decimal("0")
    discount_code = None
    invoice_id = None
    if invoice:
        invoice_id = str(invoice.get("invoice_id", ""))
        discount_amt = Decimal(str(invoice.get("discount_amt", 0)))
        discount_code = invoice.get("discount_code")
        trace.append(
            AgentStep(
                agent="reasoner",
                status="passed",
                detail=(
                    f"Invoice {invoice_id}: discount_code={discount_code!r}, "
                    f"discount_amt={discount_amt}."
                ),
            )
        )

    data_citations: list[DataCitation] = [
        DataCitation(
            source="customer",
            ref=str(customer.get("customer_id", "")),
            detail=f"signup_date={signup.isoformat()}, plan={customer.get('plan')}",
        )
    ]
    if invoice_id:
        data_citations.append(
            DataCitation(
                source="invoice",
                ref=invoice_id,
                detail=f"net={invoice.get('net')}, discount_amt={discount_amt}",
            )
        )

    policy_citations = [
        PolicyCitation(
            doc_id=passage.doc_id,
            version=passage.version,
            title="Loyalty Discount Policy",
            section=passage.section,
        )
        for passage in loyalty_passages[:2]
    ]
    if not policy_citations:
        policy_citations.append(
            PolicyCitation(
                doc_id="loyalty-discount-policy",
                version="v3",
                title="Loyalty Discount Policy",
                section="Eligibility",
            )
        )

    if meets_tenure and discount_amt == 0:
        escalate = True
        answer = (
            f"You have {membership_months} months of membership and meet the "
            f"{months_required}-month requirement under Loyalty {policy_version}, "
            f"but invoice {invoice_id} shows no loyalty discount applied. "
            "This may be a billing error — escalating for human review."
        )
        confidence = 0.75
    elif not meets_tenure:
        escalate = False
        answer = (
            f"You have about {membership_months} months of membership; Loyalty "
            f"{policy_version} requires {months_required} full months before the "
            f"10% loyalty discount applies. You become eligible on "
            f"{eligible_from.isoformat()}. "
            f"Your latest invoice ({invoice_id}) correctly shows no loyalty discount yet."
        )
        confidence = 0.92
    else:
        escalate = False
        answer = (
            f"Loyalty {policy_version} applies: {membership_months} months of "
            f"membership meets the {months_required}-month rule."
        )
        confidence = 0.9

    return LoyaltyCompareResult(
        answer=answer,
        membership_months=membership_months,
        months_required=months_required,
        eligible_from=eligible_from,
        escalate=escalate,
        confidence=confidence,
        data_citations=data_citations,
        policy_citations=policy_citations,
        trace=trace,
    )
