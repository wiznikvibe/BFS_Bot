from __future__ import annotations

from datetime import date
from typing import Any

from bfs_bot.agents.policy import PolicyRetrievalAgent, PolicyResult
from bfs_bot.agents.reasoner import compare_loyalty_eligibility
from bfs_bot.agents.structured import DataResult, StructuredDataAgent
from bfs_bot.guardrails import CrossUserScopeError
from bfs_bot.schemas import AgentStep, AnswerResponse, DataCitation, PolicyCitation

_POLICY_ONLY_MARKERS = (
    "what does the policy say",
    "what is the refund window",
    "refund window",
    "policy say",
)
_DATA_ONLY_MARKERS = (
    "last payment",
    "when was my last payment",
    "my invoice amount",
    "invoice amount",
    "how much was my invoice",
)
_POLICY_WORDS = (
    "policy",
    "refund",
    "loyalty",
    "discount",
    "late fee",
    "promo",
    "terms",
    "eligible",
    "eligibility",
)
_PERSONAL_MARKERS = (
    "my ",
    " i ",
    "why no",
    "why wasn't",
    "why was my",
    "why did i",
)
_LOYALTY_MARKERS = ("loyalty", "10%", "10 percent", "loyalty10")


def classify_route(question: str) -> str:
    normalized = f" {question.lower()} "
    has_policy_word = any(word in normalized for word in _POLICY_WORDS)
    has_personal = any(marker in normalized for marker in _PERSONAL_MARKERS)

    if any(marker in normalized for marker in _POLICY_ONLY_MARKERS):
        if not has_personal and "my invoice" not in normalized:
            return "policy_only"
    if any(marker in normalized for marker in _DATA_ONLY_MARKERS):
        if not has_policy_word:
            return "data_only"
    if has_policy_word and has_personal:
        return "hybrid"
    if has_policy_word and not has_personal:
        return "policy_only"
    if has_personal and not has_policy_word:
        return "data_only"
    return "hybrid"


def _is_loyalty_hybrid(question: str, route: str) -> bool:
    if route != "hybrid":
        return False
    normalized = question.lower()
    return any(marker in normalized for marker in _LOYALTY_MARKERS)


class Supervisor:
    def __init__(
        self,
        *,
        structured: StructuredDataAgent,
        policy: PolicyRetrievalAgent,
    ) -> None:
        self._structured = structured
        self._policy = policy

    def answer(
        self,
        question: str,
        customer_id: str,
        as_of: date | None = None,
    ) -> AnswerResponse:
        as_of = as_of or date(2026, 10, 15)
        route = classify_route(question)
        trace: list[AgentStep] = [
            AgentStep(
                agent="supervisor",
                status="passed",
                detail=f"Routed question as {route}.",
            )
        ]

        try:
            if _is_loyalty_hybrid(question, route):
                return self._answer_loyalty_hybrid(
                    question,
                    customer_id,
                    as_of,
                    route,
                    trace,
                )

            data_result: DataResult | None = None
            policy_result: PolicyResult | None = None

            if route in ("data_only", "hybrid"):
                data_result = self._structured.run(question, customer_id, as_of)
                trace.append(
                    AgentStep(
                        agent="structured_data_agent",
                        status="passed",
                        detail=f"Tools: {', '.join(data_result.tools)}.",
                    )
                )
            if route in ("policy_only", "hybrid"):
                policy_result = self._policy.run(question, as_of=as_of)
                trace.append(
                    AgentStep(
                        agent="policy_retrieval_agent",
                        status="passed",
                        detail=f"Retrieved {len(policy_result.passages)} policy passage(s).",
                    )
                )

            answer = self._compose_generic_answer(
                route,
                data_result,
                policy_result,
            )
            data_citations = _data_citations_from_rows(data_result)
            policy_citations = _policy_citations_from_passages(
                policy_result.passages if policy_result else []
            )
            return AnswerResponse(
                answer=answer,
                route=route,
                confidence=0.8,
                data_citations=data_citations,
                policy_citations=policy_citations,
                escalate=False,
                trace=trace,
            )
        except CrossUserScopeError as exc:
            trace.append(
                AgentStep(
                    agent="supervisor",
                    status="blocked",
                    detail="Cross-customer scope blocked.",
                )
            )
            return AnswerResponse(
                answer=str(exc),
                route=route,
                confidence=1.0,
                escalate=False,
                trace=trace,
            )

    def _answer_loyalty_hybrid(
        self,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
    ) -> AnswerResponse:
        customer_result = self._structured.run(
            "What is my membership and plan?",
            customer_id,
            as_of,
        )
        invoice_result = self._structured.run(
            "What is my latest invoice?",
            customer_id,
            as_of,
        )
        policy_result = self._policy.run(question, as_of=as_of)

        trace.extend(
            [
                AgentStep(
                    agent="structured_data_agent",
                    status="passed",
                    detail=(
                        "Parallel fetch: customer + latest invoice for loyalty hybrid."
                    ),
                ),
                AgentStep(
                    agent="policy_retrieval_agent",
                    status="passed",
                    detail=f"Retrieved {len(policy_result.passages)} policy passage(s).",
                ),
            ]
        )

        if not customer_result.rows:
            return AnswerResponse(
                answer=f"No customer record found for {customer_id}.",
                route=route,
                confidence=0.2,
                escalate=False,
                trace=trace,
            )

        customer = customer_result.rows[0]
        invoice = invoice_result.rows[0] if invoice_result.rows else None
        compared = compare_loyalty_eligibility(
            customer=customer,
            invoice=invoice,
            policy_passages=policy_result.passages,
            as_of=as_of,
        )
        trace.extend(compared.trace)

        return AnswerResponse(
            answer=compared.answer,
            route=route,
            confidence=compared.confidence,
            data_citations=compared.data_citations,
            policy_citations=compared.policy_citations,
            escalate=compared.escalate,
            trace=trace,
        )

    @staticmethod
    def _compose_generic_answer(
        route: str,
        data_result: DataResult | None,
        policy_result: PolicyResult | None,
    ) -> str:
        parts: list[str] = []
        if data_result and data_result.rows:
            parts.append(
                "Structured data: "
                + "; ".join(
                    f"{key}={value}"
                    for key, value in sorted(data_result.rows[0].items())
                )[:400]
            )
        if policy_result and policy_result.passages:
            snippet = policy_result.passages[0].text[:200].replace("\n", " ")
            parts.append(f"Policy excerpt ({policy_result.passages[0].version}): {snippet}")
        if not parts:
            return "I could not find enough data or policy context to answer."
        return " ".join(parts)


def _data_citations_from_rows(data_result: DataResult | None) -> list[DataCitation]:
    if not data_result or not data_result.rows:
        return []
    row = data_result.rows[0]
    if "invoice_id" in row:
        return [
            DataCitation(
                source="invoice",
                ref=str(row["invoice_id"]),
                detail=f"net={row.get('net')}",
            )
        ]
    if "customer_id" in row:
        return [
            DataCitation(
                source="customer",
                ref=str(row["customer_id"]),
                detail=f"plan={row.get('plan')}",
            )
        ]
    return []


def _policy_citations_from_passages(
    passages: list[Any],
) -> list[PolicyCitation]:
    citations: list[PolicyCitation] = []
    seen: set[tuple[str, str]] = set()
    for passage in passages:
        key = (passage.doc_id, passage.version)
        if key in seen:
            continue
        seen.add(key)
        title = passage.doc_id.replace("-", " ").title()
        citations.append(
            PolicyCitation(
                doc_id=passage.doc_id,
                version=passage.version,
                title=title,
                section=passage.section,
            )
        )
    return citations
