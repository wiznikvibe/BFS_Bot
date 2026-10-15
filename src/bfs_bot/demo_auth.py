from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, Request

PAYMENTS_CUSTOMER_ID_RE = re.compile(r"\bC\d{3}\b", re.I)


@dataclass(frozen=True)
class DemoAccount:
    username: str
    password: str
    customer_id: str
    label: str


DEMO_PERSONAS: tuple[DemoAccount, ...] = (
    DemoAccount("asha", "demo123", "C001", "Asha Verma"),
    DemoAccount("ben", "demo123", "C002", "Ben Carter"),
    DemoAccount("carla", "demo123", "C003", "Carla Gomez"),
    DemoAccount("dev", "demo123", "C004", "Dev Patel"),
    DemoAccount("elena", "demo123", "C005", "Elena Rossi"),
    DemoAccount("farid", "demo123", "C006", "Farid Khan"),
    DemoAccount("gita", "demo123", "C007", "Gita Nair"),
)

_BY_USERNAME = {account.username.lower(): account for account in DEMO_PERSONAS}
_BY_CUSTOMER_ID = {account.customer_id.upper(): account for account in DEMO_PERSONAS}


def authenticate(username: str, password: str) -> DemoAccount | None:
    account = _BY_USERNAME.get(username.strip().lower())
    if account is None or account.password != password:
        return None
    return account


def list_demo_accounts() -> list[dict[str, str]]:
    """Public hint payload: usernames and bound customer IDs only."""
    return [
        {
            "username": account.username,
            "customer_id": account.customer_id,
            "label": account.label,
        }
        for account in DEMO_PERSONAS
    ]


def get_account_by_customer_id(customer_id: str) -> DemoAccount | None:
    return _BY_CUSTOMER_ID.get(customer_id.strip().upper())


def resolve_session_customer(request: Request) -> str:
    """Return the logged-in customer_id; never trust question or body overrides."""
    customer_id = request.session.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    normalized = str(customer_id).strip().upper()
    if not PAYMENTS_CUSTOMER_ID_RE.fullmatch(normalized):
        raise HTTPException(status_code=401, detail="Invalid session customer binding.")
    return normalized
