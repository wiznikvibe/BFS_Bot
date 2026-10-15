from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from bfs_bot.guardrails import sanitize_retrieved_text
from bfs_bot.ingestion import retrieve_policy_chunks
from bfs_bot.models import PolicyChunk


@dataclass(frozen=True)
class PolicyPassage:
    doc_id: str
    version: str
    section: str
    effective_from: date
    effective_to: date | None
    text: str
    is_injection_probe: bool = False


@dataclass(frozen=True)
class PolicyResult:
    passages: list[PolicyPassage]
    as_of: date


class PolicyRetrievalAgent:
    """Semantic policy search scoped to the version in force on as_of."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def run(
        self,
        question: str,
        as_of: date,
        *,
        limit: int = 4,
        doc_id: str | None = None,
    ) -> PolicyResult:
        session = self._session_factory()
        try:
            chunks = retrieve_policy_chunks(
                session,
                question,
                as_of=as_of,
                limit=limit,
                doc_id=doc_id,
                include_injection_probes=False,
            )
            passages = [_chunk_to_passage(chunk) for chunk in chunks]
            return PolicyResult(passages=passages, as_of=as_of)
        finally:
            session.close()


def _chunk_to_passage(chunk: PolicyChunk) -> PolicyPassage:
    body = chunk.text
    if chunk.is_injection_probe:
        wrapped = body
    else:
        wrapped = sanitize_retrieved_text(body)
    return PolicyPassage(
        doc_id=chunk.doc_id,
        version=chunk.version,
        section=chunk.section,
        effective_from=chunk.effective_from,
        effective_to=chunk.effective_to,
        text=wrapped,
        is_injection_probe=chunk.is_injection_probe,
    )
