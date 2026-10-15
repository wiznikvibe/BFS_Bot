from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Protocol, runtime_checkable

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from bfs_bot.database import SessionLocal, create_schema
from bfs_bot.demo_data.policies import PolicyChunkDraft, build_policy_chunk_drafts
from bfs_bot.embeddings import cosine_similarity, hash_embedding, normalize_embedding
from bfs_bot.models import PolicyChunk


@runtime_checkable
class PolicyChunkInput(Protocol):
    doc_id: str
    version: str
    section: str
    effective_from: date
    effective_to: date | None
    text: str
    is_injection_probe: bool


def ingest_policies(session: Session, chunks: Iterable[PolicyChunkInput]) -> int:
    """Embed and persist policy chunks; replaces existing policy_chunks rows."""
    session.execute(delete(PolicyChunk))
    inserted = 0
    for chunk in chunks:
        session.add(
            PolicyChunk(
                doc_id=chunk.doc_id,
                version=chunk.version,
                section=chunk.section,
                effective_from=chunk.effective_from,
                effective_to=chunk.effective_to,
                text=chunk.text,
                embedding=hash_embedding(chunk.text),
                is_injection_probe=chunk.is_injection_probe,
            )
        )
        inserted += 1
    session.commit()
    return inserted


def effective_on(as_of: date):
    """SQL filter: chunk effective window contains as_of (inclusive)."""
    return and_(
        PolicyChunk.effective_from <= as_of,
        or_(PolicyChunk.effective_to.is_(None), PolicyChunk.effective_to >= as_of),
    )


def retrieve_policy_chunks(
    session: Session,
    query: str,
    *,
    as_of: date,
    limit: int = 4,
    doc_id: str | None = None,
    include_injection_probes: bool = False,
) -> list[PolicyChunk]:
    """Rank stored chunks by embedding similarity, scoped to the as_of effective window."""
    query_embedding = hash_embedding(query)
    stmt = select(PolicyChunk).where(effective_on(as_of))
    if doc_id is not None:
        stmt = stmt.where(PolicyChunk.doc_id == doc_id)
    if not include_injection_probes:
        stmt = stmt.where(PolicyChunk.is_injection_probe.is_(False))
    rows = list(session.scalars(stmt).all())
    ranked = sorted(
        rows,
        key=lambda row: cosine_similarity(
            query_embedding,
            normalize_embedding(row.embedding),
        ),
        reverse=True,
    )
    return ranked[:limit]


def chunk_text(text: str, max_words: int = 180, overlap: int = 30) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + max_words])
        if chunk:
            chunks.append(chunk)
    return chunks


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def main() -> None:
    create_schema()
    drafts: list[PolicyChunkDraft] = build_policy_chunk_drafts()
    with SessionLocal() as session:
        count = ingest_policies(session, drafts)
    print(f"Ingested {count} policy chunks.")


if __name__ == "__main__":
    main()
