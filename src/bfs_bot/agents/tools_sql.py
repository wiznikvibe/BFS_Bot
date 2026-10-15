from __future__ import annotations

from datetime import date
from typing import Any

from bfs_bot.guardrails import ReadonlyQueryExecutor

ToolMeta = dict[str, Any]
ToolResult = tuple[list[dict[str, Any]], ToolMeta]

_CUSTOMER_COLUMNS = (
    "customer_id",
    "name",
    "signup_date",
    "plan",
    "status",
)

_INVOICE_COLUMNS = (
    "invoice_id",
    "customer_id",
    "invoice_date",
    "due_date",
    "gross",
    "discount_code",
    "discount_amt",
    "late_fee",
    "net",
)

_PAYMENT_COLUMNS = (
    "payment_id",
    "invoice_id",
    "paid_on",
    "amount",
)


class StructuredSqlTools:
    """Curated, parameterized SELECT tools; every query binds customer_id."""

    def __init__(self, executor: ReadonlyQueryExecutor) -> None:
        self._executor = executor

    def get_customer(self, customer_id: str) -> ToolResult:
        params = {"customer_id": customer_id.upper()}
        sql = (
            "SELECT "
            + ", ".join(_CUSTOMER_COLUMNS)
            + " FROM customers WHERE customer_id = :customer_id"
        )
        rows = self._executor.execute(sql, params)
        return rows, {"tool": "get_customer", "params": params}

    def get_latest_invoice(self, customer_id: str, as_of: date) -> ToolResult:
        params = {"customer_id": customer_id.upper(), "as_of": as_of}
        sql = (
            "SELECT "
            + ", ".join(_INVOICE_COLUMNS)
            + " FROM invoices "
            "WHERE customer_id = :customer_id AND invoice_date <= :as_of "
            "ORDER BY invoice_date DESC, invoice_id DESC "
            "LIMIT 1"
        )
        rows = self._executor.execute(sql, params)
        return rows, {"tool": "get_latest_invoice", "params": params}

    def get_invoice_by_id(self, customer_id: str, invoice_id: str) -> ToolResult:
        params = {
            "customer_id": customer_id.upper(),
            "invoice_id": invoice_id.upper(),
        }
        sql = (
            "SELECT "
            + ", ".join(_INVOICE_COLUMNS)
            + " FROM invoices "
            "WHERE customer_id = :customer_id AND invoice_id = :invoice_id"
        )
        rows = self._executor.execute(sql, params)
        return rows, {"tool": "get_invoice_by_id", "params": params}

    def get_payment_for_invoice(self, customer_id: str, invoice_id: str) -> ToolResult:
        params = {
            "customer_id": customer_id.upper(),
            "invoice_id": invoice_id.upper(),
        }
        sql = (
            "SELECT "
            + ", ".join(f"p.{column}" for column in _PAYMENT_COLUMNS)
            + " FROM payments p "
            "INNER JOIN invoices i ON i.invoice_id = p.invoice_id "
            "WHERE i.customer_id = :customer_id AND p.invoice_id = :invoice_id"
        )
        rows = self._executor.execute(sql, params)
        return rows, {"tool": "get_payment_for_invoice", "params": params}

    def get_latest_payment(self, customer_id: str, as_of: date) -> ToolResult:
        params = {"customer_id": customer_id.upper(), "as_of": as_of}
        sql = (
            "SELECT "
            + ", ".join(f"p.{column}" for column in _PAYMENT_COLUMNS)
            + " FROM payments p "
            "INNER JOIN invoices i ON i.invoice_id = p.invoice_id "
            "WHERE i.customer_id = :customer_id AND p.paid_on <= :as_of "
            "ORDER BY p.paid_on DESC, p.payment_id DESC "
            "LIMIT 1"
        )
        rows = self._executor.execute(sql, params)
        return rows, {"tool": "get_latest_payment", "params": params}

    def list_recent_invoices(
        self,
        customer_id: str,
        as_of: date,
        *,
        limit: int = 10,
    ) -> ToolResult:
        params = {
            "customer_id": customer_id.upper(),
            "as_of": as_of,
            "limit": limit,
        }
        sql = (
            "SELECT "
            + ", ".join(_INVOICE_COLUMNS)
            + " FROM invoices "
            "WHERE customer_id = :customer_id AND invoice_date <= :as_of "
            "ORDER BY invoice_date DESC, invoice_id DESC "
            "LIMIT :limit"
        )
        rows = self._executor.execute(sql, params)
        return rows, {"tool": "list_recent_invoices", "params": params}
