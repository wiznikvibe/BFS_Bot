"""M2b evaluation: adversarial security probes from data/security_probes.yaml."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bfs_bot.agents.policy import PolicyRetrievalAgent
from bfs_bot.agents.structured import StructuredDataAgent
from bfs_bot.agents.supervisor import Supervisor
from bfs_bot.agents.tools_sql import StructuredSqlTools
from bfs_bot.demo_data.generator import (
    NAMED_CUSTOMERS,
    NAMED_INVOICES,
    DemoDataset,
    _payments_for_invoices,
)
from bfs_bot.demo_data.policies import build_policy_chunk_drafts
from bfs_bot.demo_data.scenarios import SecurityProbe, load_security_probes
from bfs_bot.guardrails import ReadonlyQueryExecutor
from bfs_bot.ingestion import ingest_policies
from bfs_bot.models import Base
from bfs_bot.seed import persist_demo_dataset

from tests.eval.scorers import ScoreResult, score_security_probe

AS_OF = date(2026, 10, 15)
DEFAULT_SESSION_CUSTOMER = "C001"


@pytest.fixture
def probe_db() -> sessionmaker[Session]:
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
def probe_supervisor(probe_db: sessionmaker[Session]) -> Supervisor:
    executor = ReadonlyQueryExecutor(probe_db)
    tools = StructuredSqlTools(executor)
    structured = StructuredDataAgent(tools)
    policy = PolicyRetrievalAgent(probe_db)
    return Supervisor(structured=structured, policy=policy)


def _customer_for(probe: SecurityProbe) -> str:
    return probe.customer_id or DEFAULT_SESSION_CUSTOMER


@pytest.mark.eval
@pytest.mark.parametrize(
    "probe",
    load_security_probes(),
    ids=lambda p: p.probe_id,
)
def test_security_probe(probe_supervisor: Supervisor, probe: SecurityProbe) -> None:
    customer_id = _customer_for(probe)
    response = probe_supervisor.answer(
        probe.question,
        customer_id=customer_id,
        as_of=AS_OF,
    )
    result: ScoreResult = score_security_probe(probe, response)
    assert result.passed, "; ".join(result.failures)
