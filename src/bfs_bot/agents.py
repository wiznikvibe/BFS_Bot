from __future__ import annotations

import re

from bfs_bot.llm import LLMClient, build_prompt
from bfs_bot.redaction import RedactionReport, redact_customer_record
from bfs_bot.repositories import CustomerRepository, PolicyRepository
from bfs_bot.schemas import AgentStep, AnswerResponse


CUSTOMER_ID_RE = re.compile(r"\bSME-\d{5}\b", re.I)
RAW_PII_TERMS = {"phone", "mobile", "email", "pan", "gstin", "address"}


class AgentOrchestrator:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        policy_repository: PolicyRepository,
        llm_client: LLMClient,
    ) -> None:
        self.customer_repository = customer_repository
        self.policy_repository = policy_repository
        self.llm_client = llm_client

    def answer(self, question: str) -> AnswerResponse:
        trace: list[AgentStep] = []
        normalized_question = question.lower()
        customer_id = self._extract_customer_id(question)

        if customer_id and any(term in normalized_question for term in RAW_PII_TERMS):
            trace.append(
                AgentStep(
                    agent="compliance_guard_agent",
                    status="blocked",
                    detail="Raw PII disclosure request blocked before retrieval.",
                )
            )
            return AnswerResponse(
                answer="I can't provide raw PII. I can answer using redacted customer facts and policy context.",
                redaction=RedactionReport(status="not_required"),
                trace=trace,
            )

        trace.append(
            AgentStep(
                agent="router_agent",
                status="passed",
                detail="Classified query as customer+policy." if customer_id else "Classified query as policy-only.",
            )
        )

        customer_record = None
        redacted_customer_context = None
        redaction = RedactionReport(status="not_required")
        if customer_id:
            customer_record = self.customer_repository.get_customer_by_id(customer_id)
            trace.append(
                AgentStep(
                    agent="customer_retrieval_agent",
                    status="passed" if customer_record else "not_found",
                    detail=f"Retrieved customer record for {customer_id}." if customer_record else f"No customer found for {customer_id}.",
                )
            )
            if not customer_record:
                return AnswerResponse(
                    answer=f"I couldn't find a dummy customer record for {customer_id}.",
                    redaction=redaction,
                    trace=trace,
                )

            redacted_customer_context, redaction = redact_customer_record(customer_record)
            trace.append(
                AgentStep(
                    agent="redaction_agent",
                    status=redaction.status,
                    detail=f"Redacted fields: {', '.join(redaction.redacted_fields) or 'none'}.",
                )
            )
            if redaction.status != "passed":
                trace.append(
                    AgentStep(
                        agent="compliance_guard_agent",
                        status="blocked",
                        detail="Residual PII detected after redaction.",
                    )
                )
                return AnswerResponse(
                    answer="I couldn't safely answer because customer PII remained after redaction.",
                    redaction=redaction,
                    trace=trace,
                )

        policy_chunks = self.policy_repository.search(question, limit=4)
        trace.append(
            AgentStep(
                agent="policy_retrieval_agent",
                status="passed",
                detail=f"Retrieved {len(policy_chunks)} policy chunks.",
            )
        )

        prompt = build_prompt(question, redacted_customer_context, policy_chunks)
        if customer_record is not None and redaction.status != "passed":
            raise RuntimeError("LLM call blocked because redaction did not pass.")
        answer = self.llm_client.generate(prompt)
        trace.append(
            AgentStep(
                agent="response_agent",
                status="passed",
                detail="Generated answer from redacted customer facts and policy excerpts.",
            )
        )
        return AnswerResponse(
            answer=answer,
            redaction=redaction,
            citations=[chunk.citation() for chunk in policy_chunks],
            trace=trace,
            redacted_customer_context=redacted_customer_context,
        )

    @staticmethod
    def _extract_customer_id(question: str) -> str | None:
        match = CUSTOMER_ID_RE.search(question)
        return match.group(0).upper() if match else None

