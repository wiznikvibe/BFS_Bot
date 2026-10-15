"""TDD: supervisor audit log (Task 10)."""

from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from bfs_bot.agents.policy import PolicyRetrievalAgent
from bfs_bot.agents.structured import StructuredDataAgent
from bfs_bot.agents.supervisor import Supervisor
from bfs_bot.agents.tools_sql import StructuredSqlTools
from bfs_bot.audit import AuditLogger, SupervisorAuditEvent
from bfs_bot.demo_data.generator import (
    NAMED_CUSTOMERS,
    NAMED_INVOICES,
    DemoDataset,
    _payments_for_invoices,
)
from bfs_bot.demo_data.policies import build_policy_chunk_drafts
from bfs_bot.guardrails import ReadonlyQueryExecutor
from bfs_bot.ingestion import ingest_policies
from bfs_bot.models import AuditEvent, Base, PolicyChunk
from bfs_bot.seed import persist_demo_dataset

C001_QUESTION = "Why no 10% loyalty discount?"
AS_OF = date(2026, 10, 15)


@pytest.fixture
def audit_db() -> sessionmaker[Session]:
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
def supervisor(audit_db: sessionmaker[Session]) -> Supervisor:
    executor = ReadonlyQueryExecutor(audit_db)
    tools = StructuredSqlTools(executor)
    structured = StructuredDataAgent(tools)
    policy = PolicyRetrievalAgent(audit_db)
    audit = AuditLogger(audit_db)
    return Supervisor(structured=structured, policy=policy, audit=audit)


def test_audit_logger_record_returns_id(audit_db: sessionmaker[Session]) -> None:
    logger = AuditLogger(audit_db)
    event_id = logger.record(
        SupervisorAuditEvent(
            question="test?",
            customer_id="C001",
            route="data_only",
            answer="ok",
            tool_calls=[{"tool": "get_customer", "params": {"customer_id": "C001"}}],
            policy_chunk_ids=[],
            as_of=AS_OF,
        )
    )
    assert isinstance(event_id, int)
    with audit_db() as session:
        row = session.get(AuditEvent, event_id)
        assert row is not None
        assert row.agent == "supervisor"
        assert row.status == "completed"


def test_c001_ask_persists_hybrid_audit(supervisor: Supervisor, audit_db: sessionmaker[Session]) -> None:
    response = supervisor.answer(C001_QUESTION, customer_id="C001", as_of=AS_OF)

    assert response.route == "hybrid"

    with audit_db() as session:
        events = list(session.scalars(select(AuditEvent).order_by(AuditEvent.id)))
    assert len(events) == 1
    payload = json.loads(events[0].detail)

    assert payload["route"] == "hybrid"
    assert payload["customer_id"] == "C001"
    assert payload["question"] == C001_QUESTION
    assert payload["answer"] == response.answer
    assert "2027-01-15" in payload["answer"]

    tool_params = [call["params"] for call in payload["tool_calls"]]
    assert any(p.get("customer_id") == "C001" for p in tool_params)

    with audit_db() as session:
        loyalty_ids = list(
            session.scalars(
                select(PolicyChunk.id).where(
                    PolicyChunk.doc_id == "loyalty-discount-policy",
                    PolicyChunk.version == "v3",
                    PolicyChunk.is_injection_probe.is_(False),
                )
            )
        )
    assert loyalty_ids
    recorded = set(payload["policy_chunk_ids"])
    assert recorded & set(loyalty_ids)
