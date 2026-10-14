from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete
from sqlalchemy.orm import Session

from bfs_bot.embeddings import hash_embedding
from bfs_bot.models import PolicyDocumentChunk


@dataclass(frozen=True)
class PolicySource:
    title: str
    url: str


POLICY_SOURCES = [
    PolicySource("Privacy Policy", "https://www.epaylater.in/privacy.html"),
    PolicySource("Terms and Conditions", "https://www.epaylater.in/terms_and_conditions.html"),
    PolicySource("Grievance Redressal Policy", "https://www.epaylater.in/grievance-redressal-policy.html"),
    PolicySource("Collection Agencies", "https://www.epaylater.in/Collection_Agencies.pdf"),
]

BUILTIN_POLICY_SUMMARIES = {
    "Privacy Policy": (
        "Customer information should be collected and used for stated service, compliance, "
        "risk, communication, fraud-prevention, and support purposes. Access should be "
        "limited to authorized processing needs, and customer information should be handled "
        "with appropriate safeguards."
    ),
    "Terms and Conditions": (
        "The service facilitates credit or deferred payment terms through regulated lending "
        "partners. Customers remain responsible for repayment obligations, dues, charges, "
        "and account conduct according to applicable terms."
    ),
    "Grievance Redressal Policy": (
        "Complaints should be acknowledged, tracked, investigated, and escalated through "
        "the stated grievance redressal channels when unresolved within the expected window."
    ),
    "Collection Agencies": (
        "Collection activity should be handled through authorized agencies and should follow "
        "appropriate conduct, limited disclosure, and documented engagement practices."
    ),
}


def ingest_policy_sources(session: Session, sources: list[PolicySource] = POLICY_SOURCES) -> int:
    session.execute(delete(PolicyDocumentChunk))
    inserted = 0
    with httpx.Client(timeout=20.0, follow_redirects=False) as client:
        for source in sources:
            try:
                text = fetch_policy_text(client, source)
            except Exception:
                text = BUILTIN_POLICY_SUMMARIES[source.title]
            for chunk_index, chunk in enumerate(chunk_text(text), start=1):
                session.add(
                    PolicyDocumentChunk(
                        chunk_id=f"{slugify(source.title)}-{chunk_index:03d}",
                        title=source.title,
                        section=infer_section(chunk),
                        source_url=source.url,
                        text=chunk,
                        embedding=hash_embedding(chunk),
                    )
                )
                inserted += 1
    session.commit()
    return inserted


def fetch_policy_text(client: httpx.Client, source: PolicySource) -> str:
    response = client.get(source.url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if source.url.lower().endswith(".pdf") or "pdf" in content_type:
        return extract_pdf_text(response.content)
    return extract_html_text(response.text)


def extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return normalize_whitespace(soup.get_text(" "))


def extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency available after install
        raise RuntimeError("Install the pypdf dependency to ingest PDF policy documents.") from exc
    reader = PdfReader(BytesIO(content))
    return normalize_whitespace(" ".join(page.extract_text() or "" for page in reader.pages))


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


def infer_section(chunk: str) -> str:
    words = chunk.split()[:8]
    return " ".join(words).strip(" :-") or "General"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def main() -> None:
    from bfs_bot.database import SessionLocal, create_schema

    create_schema()
    with SessionLocal() as session:
        count = ingest_policy_sources(session)
    print(f"Ingested {count} policy chunks.")


if __name__ == "__main__":
    main()

