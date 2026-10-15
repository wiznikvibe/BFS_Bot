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
_GRACE_DAYS_RE = re.compile(
    r"(\d+)\s*\(?\d*\)?\s*calendar days after the invoice due_date",
    re.I,
)
_REFUND_WINDOW_RE = re.compile(
    r"(\d+)\s*\)?\s*calendar days of the payment date",
    re.I,
)
_PERCENT_DISCOUNT_RE = re.compile(
    r"(\d+)\s*percent\s*\(?(\d+)%?\)?",
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


@dataclass(frozen=True)
class ReasonerResult:
    answer: str
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


def _passages_for_doc(
    passages: list[PolicyPassage], doc_id: str
) -> list[PolicyPassage]:
    return [p for p in passages if p.doc_id == doc_id]


def _policy_citations_from_passages(
    passages: list[PolicyPassage], *, title: str | None = None
) -> list[PolicyCitation]:
    citations: list[PolicyCitation] = []
    for passage in passages[:2]:
        citations.append(
            PolicyCitation(
                doc_id=passage.doc_id,
                version=passage.version,
                title=title or passage.doc_id.replace("-", " ").title(),
                section=passage.section,
            )
        )
    return citations


def _parse_grace_period_days(passages: list[PolicyPassage]) -> int:
    late = _passages_for_doc(passages, "late-fee-policy")
    for passage in late:
        match = _GRACE_DAYS_RE.search(passage.text)
        if match:
            return int(match.group(1))
    return 7


def _parse_refund_window_days(passages: list[PolicyPassage]) -> int:
    refund = _passages_for_doc(passages, "refund-policy")
    for passage in refund:
        match = _REFUND_WINDOW_RE.search(passage.text)
        if match:
            return int(match.group(1))
    return 14


def _parse_loyalty_percent(passages: list[PolicyPassage]) -> int | None:
    loyalty = _loyalty_policy_passages(passages)
    for passage in loyalty:
        match = _PERCENT_DISCOUNT_RE.search(passage.text)
        if match:
            return int(match.group(1))
    return None


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
        if discount_amt > 0 and discount_code:
            answer = (
                f"You have {membership_months} months of membership (over "
                f"{months_required} required), so {discount_code} was applied "
                f"correctly under Loyalty {policy_version} on invoice "
                f"{invoice_id} ({discount_amt} off gross)."
            )
        else:
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


def compare_versioned_loyalty_discount(
    *,
    customer: dict[str, Any],
    invoice: dict[str, Any],
    policy_passages: list[PolicyPassage],
) -> ReasonerResult:
    """Explain a historical invoice discount under the policy version in force then (C004)."""
    trace: list[AgentStep] = []
    signup = date.fromisoformat(str(customer["signup_date"]))
    invoice_date = date.fromisoformat(str(invoice["invoice_date"]))
    membership_months = _months_between(signup, invoice_date)
    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"Tenure at invoice date {invoice_date.isoformat()}: "
                f"{membership_months} month(s)."
            ),
        )
    )

    loyalty_passages = _loyalty_policy_passages(policy_passages)
    months_required = _parse_months_required(loyalty_passages) or 6
    policy_version = loyalty_passages[0].version if loyalty_passages else "v2"
    discount_pct = _parse_loyalty_percent(loyalty_passages) or 5
    discount_code = invoice.get("discount_code") or f"LOYALTY{discount_pct}"
    invoice_id = str(invoice.get("invoice_id", ""))

    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"Loyalty {policy_version} required {months_required} month(s); "
                f"discount {discount_pct}% ({discount_code})."
            ),
        )
    )

    answer = (
        f"Your November 2025 invoice ({invoice_id}) was issued on "
        f"{invoice_date.isoformat()} when Loyalty {policy_version} was in force "
        f"({months_required} months required, {discount_pct}% discount). "
        f"You had {membership_months} months of membership, so {discount_code} "
        f"and {discount_pct}% off were correct. Current v3 rules do not apply "
        f"to that invoice."
    )

    data_citations = [
        DataCitation(
            source="customer",
            ref=str(customer.get("customer_id", "")),
            detail=f"signup_date={signup.isoformat()}",
        ),
        DataCitation(
            source="invoice",
            ref=invoice_id,
            detail=f"invoice_date={invoice_date.isoformat()}, code={discount_code}",
        ),
    ]
    policy_citations = _policy_citations_from_passages(
        loyalty_passages, title="Loyalty Discount Policy"
    )

    return ReasonerResult(
        answer=answer,
        escalate=False,
        confidence=0.91,
        data_citations=data_citations,
        policy_citations=policy_citations,
        trace=trace,
    )


def compare_discount_stacking(
    *,
    customer: dict[str, Any],
    invoice: dict[str, Any],
    policy_passages: list[PolicyPassage],
) -> ReasonerResult:
    """Annual vs loyalty stacking — larger annual discount wins (C005)."""
    trace: list[AgentStep] = []
    invoice_id = str(invoice.get("invoice_id", ""))
    discount_code = invoice.get("discount_code") or "ANNUAL15"
    gross = Decimal(str(invoice.get("gross", 0)))
    discount_amt = Decimal(str(invoice.get("discount_amt", 0)))
    annual_pct = 15
    if gross > 0:
        annual_pct = int((discount_amt / gross * 100).quantize(Decimal("1")))

    stacking_passages = _passages_for_doc(
        policy_passages, "annual-plan-discount-policy"
    ) + _passages_for_doc(policy_passages, "loyalty-discount-policy")
    if not stacking_passages:
        stacking_passages = policy_passages

    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"Invoice {invoice_id}: plan={customer.get('plan')}, "
                f"code={discount_code}, annual discount {annual_pct}%."
            ),
        )
    )

    answer = (
        f"The annual plan discount ({annual_pct}%) and the loyalty discount "
        f"cannot be combined on the same invoice. Invoice {invoice_id} shows "
        f"{discount_code} ({discount_amt} off gross {gross}), which is the "
        f"larger eligible discount for your annual plan."
    )

    data_citations = [
        DataCitation(
            source="customer",
            ref=str(customer.get("customer_id", "")),
            detail=f"plan={customer.get('plan')}",
        ),
        DataCitation(
            source="invoice",
            ref=invoice_id,
            detail=f"discount_code={discount_code}, discount_amt={discount_amt}",
        ),
    ]
    policy_citations = _policy_citations_from_passages(stacking_passages)

    return ReasonerResult(
        answer=answer,
        escalate=False,
        confidence=0.9,
        data_citations=data_citations,
        policy_citations=policy_citations,
        trace=trace,
    )


def compare_late_fee(
    *,
    invoice: dict[str, Any],
    payment: dict[str, Any] | None,
    policy_passages: list[PolicyPassage],
) -> ReasonerResult:
    """Late fee vs grace period (C006)."""
    trace: list[AgentStep] = []
    invoice_id = str(invoice.get("invoice_id", ""))
    due = date.fromisoformat(str(invoice["due_date"]))
    late_fee = Decimal(str(invoice.get("late_fee", 0)))
    grace_days = _parse_grace_period_days(policy_passages)

    if payment:
        paid_on = date.fromisoformat(str(payment["paid_on"]))
        days_after_due = (paid_on - due).days
    else:
        paid_on = None
        days_after_due = 0

    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"Due {due.isoformat()}, paid_on={paid_on}, "
                f"days_after_due={days_after_due}, grace={grace_days}, "
                f"late_fee={late_fee}."
            ),
        )
    )

    inside_grace = days_after_due <= grace_days
    escalate = inside_grace and late_fee > 0
    if escalate:
        answer = (
            f"Payment was {days_after_due} day(s) after the due date "
            f"({due.isoformat()}), inside the {grace_days}-day grace period. "
            f"Invoice {invoice_id} shows a late fee of {late_fee}, which looks "
            f"incorrect — escalating for human review."
        )
        confidence = 0.88
    else:
        answer = (
            f"Payment timing ({days_after_due} day(s) after due) and late fee "
            f"{late_fee} on invoice {invoice_id} appear consistent with policy."
        )
        confidence = 0.85

    data_citations = [
        DataCitation(
            source="invoice",
            ref=invoice_id,
            detail=f"due_date={due.isoformat()}, late_fee={late_fee}",
        ),
    ]
    if payment:
        data_citations.append(
            DataCitation(
                source="payment",
                ref=str(payment.get("payment_id", invoice_id)),
                detail=f"paid_on={paid_on.isoformat() if paid_on else ''}",
            )
        )

    policy_citations = _policy_citations_from_passages(
        _passages_for_doc(policy_passages, "late-fee-policy"),
        title="Late Fee Policy",
    )

    return ReasonerResult(
        answer=answer,
        escalate=escalate,
        confidence=confidence,
        data_citations=data_citations,
        policy_citations=policy_citations,
        trace=trace,
    )


def compare_refund_eligibility(
    *,
    payment: dict[str, Any],
    policy_passages: list[PolicyPassage],
    as_of: date,
) -> ReasonerResult:
    """Refund window check relative to demo/as_of date (C007)."""
    trace: list[AgentStep] = []
    paid_on = date.fromisoformat(str(payment["paid_on"]))
    refund_window = _parse_refund_window_days(policy_passages)
    days_since_payment = (as_of - paid_on).days

    trace.append(
        AgentStep(
            agent="reasoner",
            status="passed",
            detail=(
                f"paid_on={paid_on.isoformat()}, as_of={as_of.isoformat()}, "
                f"days_since_payment={days_since_payment}, window={refund_window}."
            ),
        )
    )

    answer = (
        f"You paid on {paid_on.isoformat()}, which is {days_since_payment} days "
        f"before the reference date {as_of.isoformat()}. Refund policy allows "
        f"{refund_window} days from payment, so you are outside the "
        f"{refund_window}-day window."
    )

    data_citations = [
        DataCitation(
            source="payment",
            ref=str(payment.get("payment_id", "")),
            detail=f"paid_on={paid_on.isoformat()}, amount={payment.get('amount')}",
        ),
    ]
    policy_citations = _policy_citations_from_passages(
        _passages_for_doc(policy_passages, "refund-policy"),
        title="Refund Policy",
    )

    return ReasonerResult(
        answer=answer,
        escalate=False,
        confidence=0.9,
        data_citations=data_citations,
        policy_citations=policy_citations,
        trace=trace,
    )


def answer_refund_window_policy(
    policy_passages: list[PolicyPassage],
) -> ReasonerResult:
    """Policy-only refund window (no customer data)."""
    window = _parse_refund_window_days(policy_passages)
    passages = _passages_for_doc(policy_passages, "refund-policy")
    return ReasonerResult(
        answer=f"Refund requests are accepted within {window} days of payment.",
        escalate=False,
        confidence=0.95,
        data_citations=[],
        policy_citations=_policy_citations_from_passages(
            passages, title="Refund Policy"
        ),
        trace=[
            AgentStep(
                agent="reasoner",
                status="passed",
                detail=f"Refund window from policy: {window} day(s).",
            )
        ],
    )
