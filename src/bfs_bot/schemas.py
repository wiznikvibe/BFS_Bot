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
class DataCitation:
    source: str
    ref: str
    detail: str


@dataclass(frozen=True)
class PolicyCitation:
    doc_id: str
    version: str
    title: str
    section: str = ""


@dataclass(frozen=True)
class AgentStep:
    agent: str
    status: str
    detail: str


@dataclass(frozen=True)
class AnswerResponse:
    answer: str
    route: str = "hybrid"
    confidence: float = 1.0
    data_citations: list[DataCitation] = field(default_factory=list)
    policy_citations: list[PolicyCitation] = field(default_factory=list)
    escalate: bool = False
    trace: list[AgentStep] = field(default_factory=list)
    redaction: RedactionReport = field(
        default_factory=lambda: RedactionReport(status="not_required")
    )
    citations: list[Citation] = field(default_factory=list)
    redacted_customer_context: dict[str, Any] | None = None

