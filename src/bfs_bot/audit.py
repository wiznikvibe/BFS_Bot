from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from bfs_bot.agents.policy import PolicyPassage
from bfs_bot.models import AuditEvent, PolicyChunk


@dataclass(frozen=True)
class SupervisorAuditEvent:
    question: str
    customer_id: str
    route: str
    answer: str
    tool_calls: list[dict[str, Any]]
    policy_chunk_ids: list[int]
    as_of: date | None = None
    query_id: str | None = None
    status: str = "completed"


def _json_default(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class AuditLogger:
    """Persist supervisor outcomes to audit_events for compliance demo."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def resolve_policy_chunk_ids(self, passages: list[PolicyPassage]) -> list[int]:
        if not passages:
            return []
        session = self._session_factory()
        try:
            ids: list[int] = []
            for passage in passages:
                chunk_id = session.scalar(
                    select(PolicyChunk.id).where(
                        PolicyChunk.doc_id == passage.doc_id,
                        PolicyChunk.version == passage.version,
                        PolicyChunk.section == passage.section,
                    )
                )
                if chunk_id is not None:
                    ids.append(int(chunk_id))
            return ids
        finally:
            session.close()

    def record(self, event: SupervisorAuditEvent) -> int:
        query_id = event.query_id or str(uuid4())
        payload = {
            "question": event.question,
            "customer_id": event.customer_id,
            "route": event.route,
            "answer": event.answer,
            "tool_calls": event.tool_calls,
            "policy_chunk_ids": event.policy_chunk_ids,
            "as_of": event.as_of.isoformat() if event.as_of else None,
        }
        session = self._session_factory()
        try:
            row = AuditEvent(
                query_id=query_id,
                agent="supervisor",
                status=event.status,
                detail=json.dumps(payload, sort_keys=True, default=_json_default),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)
        finally:
            session.close()
