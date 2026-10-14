from __future__ import annotations

from dataclasses import asdict
from importlib.resources import files
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from bfs_bot.agents import AgentOrchestrator
from bfs_bot.config import settings
from bfs_bot.database import create_schema, get_session
from bfs_bot.llm import LLMClient, RecordingLLMClient
from bfs_bot.models import AgentAuditEvent, SMECustomer
from bfs_bot.sql_repositories import SQLCustomerRepository, SQLPolicyRepository


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=800)


class OpenAICompatibleLLMClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Answer only from the provided redacted context."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]


def get_llm_client() -> LLMClient:
    if settings.llm_api_key and settings.llm_base_url:
        return OpenAICompatibleLLMClient(settings.llm_api_key, settings.llm_base_url, settings.llm_model)
    return RecordingLLMClient()


app = FastAPI(title="BFS Bot SME Credit Assistant PoC")
static_dir = files("bfs_bot").joinpath("static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup() -> None:
    create_schema()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(static_dir.joinpath("index.html")))


@app.post("/api/ask")
def ask(request: AskRequest, session: Session = Depends(get_session)) -> dict:
    query_id = str(uuid4())
    orchestrator = AgentOrchestrator(
        customer_repository=SQLCustomerRepository(session),
        policy_repository=SQLPolicyRepository(session),
        llm_client=get_llm_client(),
    )
    response = orchestrator.answer(request.question)
    for step in response.trace:
        session.add(
            AgentAuditEvent(
                query_id=query_id,
                agent=step.agent,
                status=step.status,
                detail=step.detail,
            )
        )
    session.commit()
    payload = asdict(response)
    payload["query_id"] = query_id
    return payload


@app.get("/api/demo-customers")
def demo_customers(session: Session = Depends(get_session)) -> dict:
    customer_ids = session.scalars(
        select(SMECustomer.customer_id).order_by(SMECustomer.customer_id).limit(12)
    ).all()
    return {"customer_ids": customer_ids}


def main() -> None:
    import uvicorn

    uvicorn.run("bfs_bot.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()

