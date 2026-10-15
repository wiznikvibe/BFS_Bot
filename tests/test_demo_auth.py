from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bfs_bot.api import app, resolve_customer_id
from bfs_bot.demo_auth import (
    DEMO_PERSONAS,
    authenticate,
    list_demo_accounts,
    resolve_session_customer,
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("bfs_bot.api.create_schema", lambda: None)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("username", "customer_id"),
    [
        ("asha", "C001"),
        ("ben", "C002"),
        ("carla", "C003"),
        ("dev", "C004"),
        ("elena", "C005"),
        ("farid", "C006"),
        ("gita", "C007"),
    ],
)
def test_authenticate_maps_persona_to_customer_id(username: str, customer_id: str) -> None:
    account = authenticate(username, "demo123")
    assert account is not None
    assert account.customer_id == customer_id


def test_authenticate_rejects_bad_password() -> None:
    assert authenticate("asha", "wrong") is None


def test_list_demo_accounts_exposes_usernames_not_passwords() -> None:
    accounts = list_demo_accounts()
    assert {item["username"] for item in accounts} == {p.username for p in DEMO_PERSONAS}
    assert all("password" not in item for item in accounts)


def test_resolve_customer_id_uses_session_only() -> None:
    assert (
        resolve_customer_id(
            "Tell me about C002 invoices",
            "C003",
            "C001",
        )
        == "C001"
    )
    assert resolve_customer_id("What is my balance?", "C003", "C001") == "C001"
    assert resolve_customer_id("What is my balance?", None, None) is None


def test_unauthenticated_me_fails(client: TestClient) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401


def test_login_session_and_me_supply_customer_id(client: TestClient) -> None:
    login = client.post("/api/login", json={"username": "asha", "password": "demo123"})
    assert login.status_code == 200
    assert login.json()["customer_id"] == "C001"

    session = client.get("/api/session")
    assert session.status_code == 200
    body = session.json()
    assert body["authenticated"] is True
    assert body["customer_id"] == "C001"

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["customer_id"] == "C001"


def test_question_mentioning_other_customer_does_not_change_scope(client: TestClient) -> None:
    client.post("/api/login", json={"username": "asha", "password": "demo123"})
    response = client.post(
        "/api/ask",
        json={"question": "Show C002 invoice totals", "customer_id": "C002"},
    )
    assert response.status_code == 200
    assert response.json()["resolved_customer_id"] == "C001"
