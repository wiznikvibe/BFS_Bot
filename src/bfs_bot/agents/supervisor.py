from __future__ import annotations

from datetime import date
from typing import Any

from bfs_bot.agents.policy import PolicyPassage, PolicyRetrievalAgent, PolicyResult
from bfs_bot.audit import AuditLogger, SupervisorAuditEvent
from bfs_bot.agents.reasoner import (
    answer_refund_window_policy,
    compare_discount_stacking,
    compare_late_fee,
    compare_loyalty_eligibility,
    compare_refund_eligibility,
    compare_versioned_loyalty_discount,
)
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
_LOYALTY_MARKERS = ("loyalty", "10%", "10 percent", "loyalty10", "10% lower")
_VERSIONING_MARKERS = ("november 2025", "in 2025", "2025 invoice")
_STACKING_MARKERS = ("both", "annual", "loyalty")
_LATE_FEE_MARKERS = ("late fee",)
_REFUND_ELIGIBILITY_MARKERS = ("refund", "get a refund", "still get")


def classify_route(question: str) -> str:
    normalized = f" {question.lower()} "
    has_policy_word = any(word in normalized for word in _POLICY_WORDS)
    has_personal = any(marker in normalized for marker in _PERSONAL_MARKERS)
    if "%" in question and has_personal:
        has_policy_word = True

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
    if any(marker in normalized for marker in _VERSIONING_MARKERS):
        return False
    if "both" in normalized and "annual" in normalized:
        return False
    return any(marker in normalized for marker in _LOYALTY_MARKERS)


def _hybrid_handler_kind(question: str, route: str) -> str | None:
    if route != "hybrid":
        return None
    normalized = question.lower()
    if any(m in normalized for m in _VERSIONING_MARKERS) or (
        "discount" in normalized and "2025" in normalized
    ):
        return "versioning"
    if all(m in normalized for m in ("annual", "loyalty")) and "both" in normalized:
        return "stacking"
    if any(m in normalized for m in _LATE_FEE_MARKERS):
        return "late_fee"
    if any(m in normalized for m in _REFUND_ELIGIBILITY_MARKERS) and (
        "can i" in normalized or "still" in normalized
    ):
        return "refund"
    return None


def _is_refund_window_policy_only(question: str, route: str) -> bool:
    if route != "policy_only":
        return False
    normalized = question.lower()
    return "refund window" in normalized or (
        "refund" in normalized and "window" in normalized
    )


class Supervisor:
    def __init__(
        self,
        *,
        structured: StructuredDataAgent,
        policy: PolicyRetrievalAgent,
        audit: AuditLogger | None = None,
    ) -> None:
        self._structured = structured
        self._policy = policy
        self._audit = audit

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
            if _is_refund_window_policy_only(question, route):
                return self._answer_refund_policy_only(
                    question,
                    customer_id,
                    as_of,
                    route,
                    trace,
                )

            hybrid_kind = _hybrid_handler_kind(question, route)
            if hybrid_kind == "versioning":
                return self._answer_versioning_hybrid(
                    question, customer_id, as_of, route, trace
                )
            if hybrid_kind == "stacking":
                return self._answer_stacking_hybrid(
                    question, customer_id, as_of, route, trace
                )
            if hybrid_kind == "late_fee":
                return self._answer_late_fee_hybrid(
                    question, customer_id, as_of, route, trace
                )
            if hybrid_kind == "refund":
                return self._answer_refund_hybrid(
                    question, customer_id, as_of, route, trace
                )

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
            response = AnswerResponse(
                answer=answer,
                route=route,
                confidence=0.8,
                data_citations=data_citations,
                policy_citations=policy_citations,
                escalate=False,
                trace=trace,
            )
            tool_calls = _tool_calls_from_data(data_result)
            passages = policy_result.passages if policy_result else []
            self._persist_audit(
                question=question,
                customer_id=customer_id,
                as_of=as_of,
                response=response,
                tool_calls=tool_calls,
                policy_passages=passages,
            )
            return response
        except CrossUserScopeError as exc:
            trace.append(
                AgentStep(
                    agent="supervisor",
                    status="blocked",
                    detail="Cross-customer scope blocked.",
                )
            )
            response = AnswerResponse(
                answer=str(exc),
                route=route,
                confidence=1.0,
                escalate=False,
                trace=trace,
            )
            self._persist_audit(
                question=question,
                customer_id=customer_id,
                as_of=as_of,
                response=response,
                tool_calls=[],
                policy_passages=[],
                status="blocked",
            )
            return response

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

        tool_calls = _tool_calls_from_results(customer_result, invoice_result)

        if not customer_result.rows:
            response = AnswerResponse(
                answer=f"No customer record found for {customer_id}.",
                route=route,
                confidence=0.2,
                escalate=False,
                trace=trace,
            )
            self._persist_audit(
                question=question,
                customer_id=customer_id,
                as_of=as_of,
                response=response,
                tool_calls=tool_calls,
                policy_passages=policy_result.passages,
            )
            return response

        customer = customer_result.rows[0]
        invoice = invoice_result.rows[0] if invoice_result.rows else None
        compared = compare_loyalty_eligibility(
            customer=customer,
            invoice=invoice,
            policy_passages=policy_result.passages,
            as_of=as_of,
        )
        trace.extend(compared.trace)

        response = AnswerResponse(
            answer=compared.answer,
            route=route,
            confidence=compared.confidence,
            data_citations=compared.data_citations,
            policy_citations=compared.policy_citations,
            escalate=compared.escalate,
            trace=trace,
        )
        self._persist_audit(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            response=response,
            tool_calls=tool_calls,
            policy_passages=policy_result.passages,
        )
        return response

    def _answer_from_reasoner(
        self,
        *,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
        compared: Any,
        tool_calls: list[dict[str, Any]],
        policy_passages: list[PolicyPassage],
    ) -> AnswerResponse:
        trace.extend(compared.trace)
        response = AnswerResponse(
            answer=compared.answer,
            route=route,
            confidence=compared.confidence,
            data_citations=compared.data_citations,
            policy_citations=compared.policy_citations,
            escalate=compared.escalate,
            trace=trace,
        )
        self._persist_audit(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            response=response,
            tool_calls=tool_calls,
            policy_passages=policy_passages,
        )
        return response

    def _answer_refund_policy_only(
        self,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
    ) -> AnswerResponse:
        policy_result = self._policy.run(question, as_of=as_of, doc_id="refund-policy")
        trace.append(
            AgentStep(
                agent="policy_retrieval_agent",
                status="passed",
                detail=f"Retrieved {len(policy_result.passages)} refund policy passage(s).",
            )
        )
        compared = answer_refund_window_policy(policy_result.passages)
        return self._answer_from_reasoner(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            route=route,
            trace=trace,
            compared=compared,
            tool_calls=[],
            policy_passages=policy_result.passages,
        )

    def _answer_versioning_hybrid(
        self,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
    ) -> AnswerResponse:
        customer_result = self._structured.run(
            "What is my membership and plan?", customer_id, as_of
        )
        invoice_result = self._structured.run(
            "What is my latest invoice?", customer_id, as_of
        )
        invoice = invoice_result.rows[0] if invoice_result.rows else {}
        invoice_date = date.fromisoformat(str(invoice.get("invoice_date", as_of)))
        policy_result = self._policy.run(question, as_of=invoice_date)
        trace.extend(
            [
                AgentStep(
                    agent="structured_data_agent",
                    status="passed",
                    detail="Fetched customer and invoice for versioning hybrid.",
                ),
                AgentStep(
                    agent="policy_retrieval_agent",
                    status="passed",
                    detail=(
                        f"Policy as_of invoice date {invoice_date.isoformat()} "
                        f"({len(policy_result.passages)} passage(s))."
                    ),
                ),
            ]
        )
        compared = compare_versioned_loyalty_discount(
            customer=customer_result.rows[0],
            invoice=invoice,
            policy_passages=policy_result.passages,
        )
        tool_calls = _tool_calls_from_results(customer_result, invoice_result)
        return self._answer_from_reasoner(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            route=route,
            trace=trace,
            compared=compared,
            tool_calls=tool_calls,
            policy_passages=policy_result.passages,
        )

    def _answer_stacking_hybrid(
        self,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
    ) -> AnswerResponse:
        customer_result = self._structured.run(
            "What is my membership and plan?", customer_id, as_of
        )
        invoice_result = self._structured.run(
            "What is my latest invoice?", customer_id, as_of
        )
        policy_result = self._policy.run(question, as_of=as_of)
        trace.extend(
            [
                AgentStep(
                    agent="structured_data_agent",
                    status="passed",
                    detail="Fetched customer and invoice for stacking hybrid.",
                ),
                AgentStep(
                    agent="policy_retrieval_agent",
                    status="passed",
                    detail=f"Retrieved {len(policy_result.passages)} policy passage(s).",
                ),
            ]
        )
        compared = compare_discount_stacking(
            customer=customer_result.rows[0],
            invoice=invoice_result.rows[0],
            policy_passages=policy_result.passages,
        )
        tool_calls = _tool_calls_from_results(customer_result, invoice_result)
        return self._answer_from_reasoner(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            route=route,
            trace=trace,
            compared=compared,
            tool_calls=tool_calls,
            policy_passages=policy_result.passages,
        )

    def _answer_late_fee_hybrid(
        self,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
    ) -> AnswerResponse:
        invoice_result = self._structured.run(
            "What is my latest invoice?", customer_id, as_of
        )
        invoice = invoice_result.rows[0]
        invoice_id = str(invoice["invoice_id"])
        payment_result = self._structured.run(
            f"Payment for invoice {invoice_id}",
            customer_id,
            as_of,
        )
        policy_result = self._policy.run(question, as_of=as_of, doc_id="late-fee-policy")
        trace.extend(
            [
                AgentStep(
                    agent="structured_data_agent",
                    status="passed",
                    detail="Fetched invoice and payment for late-fee hybrid.",
                ),
                AgentStep(
                    agent="policy_retrieval_agent",
                    status="passed",
                    detail=f"Retrieved {len(policy_result.passages)} late-fee passage(s).",
                ),
            ]
        )
        payment = payment_result.rows[0] if payment_result.rows else None
        compared = compare_late_fee(
            invoice=invoice,
            payment=payment,
            policy_passages=policy_result.passages,
        )
        tool_calls = _tool_calls_from_results(invoice_result, payment_result)
        return self._answer_from_reasoner(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            route=route,
            trace=trace,
            compared=compared,
            tool_calls=tool_calls,
            policy_passages=policy_result.passages,
        )

    def _answer_refund_hybrid(
        self,
        question: str,
        customer_id: str,
        as_of: date,
        route: str,
        trace: list[AgentStep],
    ) -> AnswerResponse:
        invoice_result = self._structured.run(
            "What is my latest invoice?", customer_id, as_of
        )
        invoice = invoice_result.rows[0]
        invoice_id = str(invoice["invoice_id"])
        payment_result = self._structured.run(
            f"Payment for invoice {invoice_id}",
            customer_id,
            as_of,
        )
        policy_result = self._policy.run(question, as_of=as_of, doc_id="refund-policy")
        trace.extend(
            [
                AgentStep(
                    agent="structured_data_agent",
                    status="passed",
                    detail="Fetched payment for refund eligibility hybrid.",
                ),
                AgentStep(
                    agent="policy_retrieval_agent",
                    status="passed",
                    detail=f"Retrieved {len(policy_result.passages)} refund passage(s).",
                ),
            ]
        )
        payment = payment_result.rows[0]
        compared = compare_refund_eligibility(
            payment=payment,
            policy_passages=policy_result.passages,
            as_of=as_of,
        )
        tool_calls = _tool_calls_from_results(invoice_result, payment_result)
        return self._answer_from_reasoner(
            question=question,
            customer_id=customer_id,
            as_of=as_of,
            route=route,
            trace=trace,
            compared=compared,
            tool_calls=tool_calls,
            policy_passages=policy_result.passages,
        )

    def _persist_audit(
        self,
        *,
        question: str,
        customer_id: str,
        as_of: date,
        response: AnswerResponse,
        tool_calls: list[dict[str, Any]],
        policy_passages: list[PolicyPassage],
        status: str = "completed",
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            SupervisorAuditEvent(
                question=question,
                customer_id=customer_id,
                route=response.route,
                answer=response.answer,
                tool_calls=tool_calls,
                policy_chunk_ids=self._audit.resolve_policy_chunk_ids(policy_passages),
                as_of=as_of,
                status=status,
            )
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


def _tool_calls_from_data(data_result: DataResult | None) -> list[dict[str, Any]]:
    if not data_result or not data_result.tools:
        return []
    tool = data_result.tools[0]
    return [{"tool": tool, "params": dict(data_result.bound_params)}]


def _tool_calls_from_results(*results: DataResult) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for result in results:
        calls.extend(_tool_calls_from_data(result))
    return calls


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
    if "payment_id" in row:
        return [
            DataCitation(
                source="payment",
                ref=str(row["payment_id"]),
                detail=f"paid_on={row.get('paid_on')}, amount={row.get('amount')}",
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
