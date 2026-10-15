"""TDD: structured-data agent with scoped SQL tools (Task 7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bfs_bot.agents.structured import DataResult, StructuredDataAgent
from bfs_bot.agents.tools_sql import StructuredSqlTools
from bfs_bot.demo_data.generator import (
    NAMED_CUSTOMERS,
    NAMED_INVOICES,
    DemoDataset,
    _payments_for_invoices,
)
from bfs_bot.guardrails import CrossUserScopeError, ReadonlyQueryExecutor
from bfs_bot.models import Base
from bfs_bot.seed import persist_demo_dataset


@pytest.fixture
def scoped_db() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    invoices = list(NAMED_INVOICES)
    dataset = DemoDataset(
        customers=list(NAMED_CUSTOMERS),
        invoices=invoices,
        payments=_payments_for_invoices(invoices),
        discount_codes=[],
        policy_chunks=[],
    )
    with factory() as session:
        persist_demo_dataset(session, dataset)
    return factory


@pytest.fixture
def structured_agent(scoped_db: sessionmaker[Session]) -> StructuredDataAgent:
    executor = ReadonlyQueryExecutor(scoped_db)
    tools = StructuredSqlTools(executor)
    return StructuredDataAgent(tools)


def test_c001_latest_invoice_net_and_discount(structured_agent: StructuredDataAgent) -> None:
    result = structured_agent.run(
        "What is my latest invoice?",
        customer_id="C001",
        as_of=date(2026, 10, 15),
    )

    assert isinstance(result, DataResult)
    assert result.tools == ["get_latest_invoice"]
    assert result.bound_params["customer_id"] == "C001"
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["invoice_id"] == "INV-1001"
    assert Decimal(str(row["net"])) == Decimal("100.00")
    assert Decimal(str(row["discount_amt"])) == Decimal("0.00")


def test_get_customer_tool_includes_customer_id_param(
    scoped_db: sessionmaker[Session],
) -> None:
    tools = StructuredSqlTools(ReadonlyQueryExecutor(scoped_db))
    rows, meta = tools.get_customer("C001")

    assert meta["tool"] == "get_customer"
    assert meta["params"]["customer_id"] == "C001"
    assert rows[0]["name"] == "Asha Verma"
    assert rows[0]["plan"] == "monthly"


def test_get_invoice_by_id_scoped_to_customer(scoped_db: sessionmaker[Session]) -> None:
    tools = StructuredSqlTools(ReadonlyQueryExecutor(scoped_db))
    rows, meta = tools.get_invoice_by_id("C002", "INV-1002")

    assert meta["tool"] == "get_invoice_by_id"
    assert meta["params"] == {"customer_id": "C002", "invoice_id": "INV-1002"}
    assert rows[0]["discount_code"] == "LOYALTY10"


def test_get_invoice_by_id_returns_empty_for_other_customers_invoice(
    scoped_db: sessionmaker[Session],
) -> None:
    tools = StructuredSqlTools(ReadonlyQueryExecutor(scoped_db))
    rows, meta = tools.get_invoice_by_id("C001", "INV-1002")

    assert meta["params"]["customer_id"] == "C001"
    assert rows == []


def test_get_payment_for_invoice_joins_customer_scope(
    scoped_db: sessionmaker[Session],
) -> None:
    tools = StructuredSqlTools(ReadonlyQueryExecutor(scoped_db))
    rows, meta = tools.get_payment_for_invoice("C002", "INV-1002")

    assert meta["tool"] == "get_payment_for_invoice"
    assert meta["params"]["customer_id"] == "C002"
    assert meta["params"]["invoice_id"] == "INV-1002"
    assert len(rows) == 1
    assert Decimal(str(rows[0]["amount"])) == Decimal("90.00")


def test_list_recent_invoices_respects_as_of(structured_agent: StructuredDataAgent) -> None:
    result = structured_agent.run(
        "List my recent invoices",
        customer_id="C002",
        as_of=date(2026, 10, 15),
    )

    assert result.tools == ["list_recent_invoices"]
    assert result.bound_params["customer_id"] == "C002"
    assert result.bound_params["as_of"] == date(2026, 10, 15)
    assert all(row["customer_id"] == "C002" for row in result.rows)
    assert result.rows[0]["invoice_id"] == "INV-1002"


def test_question_with_other_customer_id_raises_scope_error(
    structured_agent: StructuredDataAgent,
) -> None:
    with pytest.raises(CrossUserScopeError):
        structured_agent.run(
            "Show C002 latest invoice",
            customer_id="C001",
            as_of=date(2026, 10, 15),
        )


def test_invoice_id_in_question_routes_to_get_invoice_by_id(
    structured_agent: StructuredDataAgent,
) -> None:
    result = structured_agent.run(
        "Details for invoice INV-1002",
        customer_id="C002",
        as_of=date(2026, 10, 15),
    )

    assert result.tools == ["get_invoice_by_id"]
    assert result.bound_params["invoice_id"] == "INV-1002"
    assert result.bound_params["customer_id"] == "C002"


def test_payment_question_routes_to_get_payment_for_invoice(
    structured_agent: StructuredDataAgent,
) -> None:
    result = structured_agent.run(
        "When was payment received for INV-1002?",
        customer_id="C002",
        as_of=date(2026, 10, 15),
    )

    assert result.tools == ["get_payment_for_invoice"]
    assert result.bound_params["customer_id"] == "C002"
    assert "paid_on" in result.rows[0]
