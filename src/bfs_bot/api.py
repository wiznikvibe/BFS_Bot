from __future__ import annotations

from dataclasses import asdict
from importlib.resources import files
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from bfs_bot.agents.policy import PolicyRetrievalAgent
from bfs_bot.agents.structured import StructuredDataAgent
from bfs_bot.agents.supervisor import Supervisor
from bfs_bot.agents.tools_sql import StructuredSqlTools
from bfs_bot.config import settings
from bfs_bot.database import SessionLocal, create_schema, get_session
from bfs_bot.guardrails import ReadonlyQueryExecutor
from bfs_bot.schemas import AnswerResponse
from bfs_bot.demo_auth import (
    authenticate,
    get_account_by_customer_id,
    list_demo_accounts,
    resolve_session_customer,
)
from bfs_bot.models import Customer


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=800)
    customer_id: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)


def build_supervisor(session_factory=SessionLocal) -> Supervisor:
    executor = ReadonlyQueryExecutor(session_factory)
    tools = StructuredSqlTools(executor)
    return Supervisor(
        structured=StructuredDataAgent(tools),
        policy=PolicyRetrievalAgent(session_factory),
    )


def answer_response_to_dict(response: AnswerResponse) -> dict:
    payload = asdict(response)
    payload["redaction"] = asdict(response.redaction)
    return payload


def resolve_customer_id(
    question: str,
    request_customer_id: str | None,
    session_customer_id: str | None,
) -> str | None:
    """Scope queries to the session-bound customer only (ignore question/body IDs)."""
    del question, request_customer_id
    if session_customer_id:
        return str(session_customer_id).strip().upper()
    return None


app = FastAPI(title="BFS Bot Payments + Policy Assistant PoC")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=False,
)
static_dir = files("bfs_bot").joinpath("static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup() -> None:
    create_schema()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(static_dir.joinpath("index.html")))


@app.post("/api/login")
def login(payload: LoginRequest, request: Request) -> dict:
    account = authenticate(payload.username, payload.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid demo credentials.")
    request.session["customer_id"] = account.customer_id
    request.session["username"] = account.username
    return {
        "authenticated": True,
        "username": account.username,
        "customer_id": account.customer_id,
        "label": account.label,
    }


@app.post("/api/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"authenticated": False, "customer_id": None}


@app.get("/api/session")
def session_status(request: Request) -> dict:
    customer_id = request.session.get("customer_id")
    username = request.session.get("username")
    return {
        "authenticated": bool(customer_id),
        "customer_id": customer_id,
        "username": username,
        "demo_accounts": list_demo_accounts(),
    }


@app.get("/api/me")
def me(request: Request) -> dict:
    customer_id = resolve_session_customer(request)
    username = request.session.get("username")
    account = get_account_by_customer_id(customer_id)
    return {
        "username": username,
        "customer_id": customer_id,
        "label": account.label if account else None,
    }


@app.post("/api/ask")
def ask(request_body: AskRequest, request: Request) -> dict:
    bound_customer_id = resolve_session_customer(request)
    resolved = resolve_customer_id(
        request_body.question,
        request_body.customer_id,
        bound_customer_id,
    )
    if not resolved:
        raise HTTPException(status_code=401, detail="Login required to ask questions.")

    supervisor = build_supervisor()
    response = supervisor.answer(request_body.question, customer_id=resolved)
    query_id = str(uuid4())
    body = answer_response_to_dict(response)
    body["query_id"] = query_id
    body["resolved_customer_id"] = resolved
    return body


@app.get("/api/demo-customers")
def demo_customers(session: Session = Depends(get_session)) -> dict:
    rows = session.execute(
        select(
            Customer.customer_id,
            Customer.name,
            Customer.plan,
            Customer.status,
        )
        .order_by(Customer.customer_id)
        .limit(12)
    ).all()
    personas = [
        {
            "customer_id": row.customer_id,
            "name": row.name,
            "plan": row.plan,
            "status": row.status,
        }
        for row in rows
    ]
    return {
        "customer_ids": [persona["customer_id"] for persona in personas],
        "personas": personas,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("bfs_bot.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
