"""TDD: thin E2E supervisor slice — scenario C001 (Task 9 / M1)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bfs_bot.agents.policy import PolicyRetrievalAgent
from bfs_bot.agents.structured import StructuredDataAgent
from bfs_bot.agents.supervisor import Supervisor, classify_route
from bfs_bot.agents.tools_sql import StructuredSqlTools
from bfs_bot.demo_data.generator import (
    NAMED_CUSTOMERS,
    NAMED_INVOICES,
    DemoDataset,
    _payments_for_invoices,
)
from bfs_bot.demo_data.policies import build_policy_chunk_drafts
from bfs_bot.guardrails import ReadonlyQueryExecutor
from bfs_bot.ingestion import ingest_policies
from bfs_bot.models import Base
from bfs_bot.seed import persist_demo_dataset

C001_QUESTION = "Why no 10% loyalty discount?"
AS_OF = date(2026, 10, 15)


@pytest.fixture
def supervisor_db() -> sessionmaker[Session]:
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
        ingest_policies(session, build_policy_chunk_drafts())
    return factory


@pytest.fixture
def supervisor(supervisor_db: sessionmaker[Session]) -> Supervisor:
    executor = ReadonlyQueryExecutor(supervisor_db)
    tools = StructuredSqlTools(executor)
    structured = StructuredDataAgent(tools)
    policy = PolicyRetrievalAgent(supervisor_db)
    return Supervisor(structured=structured, policy=policy)


def test_route_classifier_for_c001() -> None:
    assert classify_route(C001_QUESTION) == "hybrid"


def test_c001_hybrid_loyalty_answer(supervisor: Supervisor) -> None:
    response = supervisor.answer(C001_QUESTION, customer_id="C001", as_of=AS_OF)

    assert response.route == "hybrid"
    assert response.escalate is False
    assert response.confidence >= 0.7

    data_refs = {c.ref for c in response.data_citations}
    assert "INV-1001" in data_refs

    policy_versions = {
        (c.doc_id, c.version) for c in response.policy_citations
    }
    assert ("loyalty-discount-policy", "v3") in policy_versions

    answer_lower = response.answer.lower()
    assert "9" in response.answer and "month" in answer_lower
    assert "12" in response.answer
    assert "2027-01-15" in response.answer
    assert any(step.agent == "supervisor" for step in response.trace)


def test_data_only_route_without_policy_words() -> None:
    assert classify_route("When was my last payment?") == "data_only"


def test_policy_only_route_without_personal_invoice() -> None:
    assert classify_route("What is the refund window?") == "policy_only"


def test_route_classifier_for_c002_invoice_percent() -> None:
    assert classify_route("Why was my invoice 10% lower?") == "hybrid"
