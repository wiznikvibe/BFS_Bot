from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from bfs_bot.agents.tools_sql import StructuredSqlTools
from bfs_bot.guardrails import assert_customer_scope

CUSTOMER_ID_RE = re.compile(r"\bC\d{3}\b", re.I)
INVOICE_ID_RE = re.compile(r"\bINV-\d+\b", re.I)

_PAYMENT_TERMS = ("payment", "paid", "pay ")
_LATEST_TERMS = ("latest", "most recent", "last invoice", "newest")
_LIST_TERMS = ("list", "show all", "recent invoices")
_MEMBERSHIP_TERMS = ("membership", "signup", "signed up", "member since", "plan type", " my plan")


@dataclass(frozen=True)
class DataResult:
    rows: list[dict[str, Any]]
    tools: list[str]
    bound_params: dict[str, Any]


class StructuredDataAgent:
    def __init__(self, tools: StructuredSqlTools) -> None:
        self._tools = tools

    def run(self, question: str, customer_id: str, as_of: date) -> DataResult:
        session_customer = assert_customer_scope(
            customer_id,
            self._extract_customer_id(question),
        )
        invoice_id = self._extract_invoice_id(question)
        normalized = question.lower()

        if invoice_id and any(term in normalized for term in _PAYMENT_TERMS):
            rows, meta = self._tools.get_payment_for_invoice(session_customer, invoice_id)
        elif invoice_id:
            rows, meta = self._tools.get_invoice_by_id(session_customer, invoice_id)
        elif any(term in normalized for term in _LIST_TERMS) and "invoice" in normalized:
            rows, meta = self._tools.list_recent_invoices(session_customer, as_of)
        elif any(term in normalized for term in _LATEST_TERMS) or (
            "invoice" in normalized and "recent" not in normalized
        ):
            rows, meta = self._tools.get_latest_invoice(session_customer, as_of)
        elif any(term in normalized for term in _MEMBERSHIP_TERMS):
            rows, meta = self._tools.get_customer(session_customer)
        elif "invoice" in normalized:
            rows, meta = self._tools.get_latest_invoice(session_customer, as_of)
        else:
            rows, meta = self._tools.get_customer(session_customer)

        return DataResult(
            rows=rows,
            tools=[meta["tool"]],
            bound_params=dict(meta["params"]),
        )

    @staticmethod
    def _extract_customer_id(question: str) -> str | None:
        match = CUSTOMER_ID_RE.search(question)
        return match.group(0).upper() if match else None

    @staticmethod
    def _extract_invoice_id(question: str) -> str | None:
        match = INVOICE_ID_RE.search(question)
        return match.group(0).upper() if match else None
