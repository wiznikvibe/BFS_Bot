from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bfs_bot.redaction import RedactionReport


@dataclass(frozen=True)
class Citation:
    source: str
    title: str
    section: str
    chunk_id: str


@dataclass(frozen=True)
class AgentStep:
    agent: str
    status: str
    detail: str


@dataclass(frozen=True)
class AnswerResponse:
    answer: str
    redaction: RedactionReport
    citations: list[Citation] = field(default_factory=list)
    trace: list[AgentStep] = field(default_factory=list)
    redacted_customer_context: dict[str, Any] | None = None

