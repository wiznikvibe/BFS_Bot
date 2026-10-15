"""Load scenario matrix and security probe fixtures from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PathType = str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_path(name: str) -> Path:
    return _repo_root() / "data" / name


@dataclass(frozen=True)
class Scenario:
    customer_id: PathType
    question: str
    path: str
    tags: list[str] = field(default_factory=list)
    expected: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SecurityProbe:
    probe_id: str
    customer_id: PathType
    question: str
    tags: list[str] = field(default_factory=list)
    expected: dict[str, Any] = field(default_factory=dict)


def _normalize_customer_id(raw: Any) -> PathType:
    if raw is None:
        return None
    return str(raw)


def _parse_scenario(raw: dict[str, Any]) -> Scenario:
    return Scenario(
        customer_id=_normalize_customer_id(raw.get("customer_id")),
        question=str(raw["question"]),
        path=str(raw["path"]),
        tags=list(raw.get("tags") or []),
        expected=dict(raw.get("expected") or {}),
    )


def _parse_probe(raw: dict[str, Any]) -> SecurityProbe:
    return SecurityProbe(
        probe_id=str(raw["probe_id"]),
        customer_id=_normalize_customer_id(raw.get("customer_id")),
        question=str(raw["question"]),
        tags=list(raw.get("tags") or []),
        expected=dict(raw.get("expected") or {}),
    )


def load_scenarios() -> list[Scenario]:
    path = _data_path("scenarios.yaml")
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    rows = doc.get("scenarios") or []
    return [_parse_scenario(row) for row in rows]


def load_security_probes() -> list[SecurityProbe]:
    path = _data_path("security_probes.yaml")
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    rows = doc.get("probes") or []
    return [_parse_probe(row) for row in rows]
