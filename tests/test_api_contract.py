"""API contract: /api/ask JSON matches AnswerResponse shape."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bfs_bot.api import answer_response_to_dict, app
from bfs_bot.redaction import RedactionReport
from bfs_bot.schemas import AgentStep, AnswerResponse, DataCitation, PolicyCitation

_ANSWER_RESPONSE_KEYS = frozenset(
    {
        "answer",
        "route",
        "confidence",
        "data_citations",
        "policy_citations",
        "escalate",
        "trace",
        "redaction",
        "citations",
        "redacted_customer_context",
    }
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("bfs_bot.api.create_schema", lambda: None)
    with TestClient(app) as test_client:
        yield test_client


def test_answer_response_to_dict_includes_core_fields() -> None:
    response = AnswerResponse(
        answer="Example",
        route="hybrid",
        confidence=0.92,
        data_citations=[DataCitation(source="invoice", ref="INV-1001", detail="net 100")],
        policy_citations=[
            PolicyCitation(doc_id="loyalty-discount-policy", version="v3", title="Loyalty")
        ],
        escalate=False,
        trace=[AgentStep(agent="supervisor", status="ok", detail="routed hybrid")],
        redaction=RedactionReport(status="applied", redacted_fields=["name"]),
    )
    body = answer_response_to_dict(response)
    assert _ANSWER_RESPONSE_KEYS.issubset(body.keys())
    assert body["redaction"]["status"] == "applied"
    assert body["data_citations"][0]["ref"] == "INV-1001"
    assert body["policy_citations"][0]["version"] == "v3"


def test_ask_json_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = AnswerResponse(
        answer="Stub answer",
        route="policy",
        confidence=1.0,
        policy_citations=[
            PolicyCitation(doc_id="refund-policy", version="v1", title="Refunds", section="Window")
        ],
        escalate=True,
        trace=[AgentStep(agent="policy", status="ok", detail="retrieved chunks")],
    )

    class _StubSupervisor:
        def answer(self, question: str, customer_id: str | None = None) -> AnswerResponse:
            del question, customer_id
            return stub

    monkeypatch.setattr("bfs_bot.api.build_supervisor", lambda: _StubSupervisor())

    client.post("/api/login", json={"username": "asha", "password": "demo123"})
    response = client.post("/api/ask", json={"question": "What is the refund window?"})
    assert response.status_code == 200
    body = response.json()

    assert _ANSWER_RESPONSE_KEYS.issubset(body.keys())
    assert body["answer"] == "Stub answer"
    assert body["route"] == "policy"
    assert body["escalate"] is True
    assert body["resolved_customer_id"] == "C001"
    assert "query_id" in body
    assert isinstance(body["trace"], list)
    assert body["trace"][0]["agent"] == "policy"
