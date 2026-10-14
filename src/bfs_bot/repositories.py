from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bfs_bot.schemas import Citation


class CustomerRepository(Protocol):
    def get_customer_by_id(self, customer_id: str) -> dict | None:
        ...


class PolicyRepository(Protocol):
    def search(self, query: str, limit: int = 4) -> list["PolicyChunk"]:
        ...


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    title: str
    section: str
    source: str
    text: str

    def citation(self) -> Citation:
        return Citation(
            source=self.source,
            title=self.title,
            section=self.section,
            chunk_id=self.chunk_id,
        )


class InMemoryCustomerRepository:
    def __init__(self) -> None:
        self._customers = {
            "SME-10023": {
                "customer_id": "SME-10023",
                "business_name": "Mehta Packaging LLP",
                "contact_name": "Riya Mehta",
                "email": "riya.mehta@example.com",
                "phone": "+91 98765 43210",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
                "registered_address": "42 MG Road, Pune",
                "industry": "Packaging and wholesale supplies",
                "risk_tier": "B",
                "credit_limit": 250000,
                "utilized_amount": 173500,
                "available_limit": 76500,
                "account_status": "active",
                "next_due_date": "2026-10-22",
                "overdue_amount": 0,
            }
        }

    def get_customer_by_id(self, customer_id: str) -> dict | None:
        return self._customers.get(customer_id.upper())


class InMemoryPolicyRepository:
    def __init__(self) -> None:
        self._chunks = [
            PolicyChunk(
                chunk_id="privacy-001",
                title="Privacy Policy",
                section="Collection and use of information",
                source="https://www.epaylater.in/privacy.html",
                text=(
                    "Customer data should be used only for stated service, compliance, "
                    "risk, communication, and support purposes, with appropriate safeguards."
                ),
            ),
            PolicyChunk(
                chunk_id="terms-001",
                title="Terms and Conditions",
                section="Credit services",
                source="https://www.epaylater.in/terms_and_conditions.html",
                text=(
                    "The service facilitates credit or payment terms through regulated "
                    "lending partners, and customer obligations depend on account status, "
                    "dues, and applicable terms."
                ),
            ),
            PolicyChunk(
                chunk_id="grievance-001",
                title="Grievance Redressal Policy",
                section="Escalation",
                source="https://www.epaylater.in/grievance-redressal-policy.html",
                text=(
                    "Customer complaints should be tracked, acknowledged, and escalated "
                    "through the stated grievance redressal process when unresolved."
                ),
            ),
            PolicyChunk(
                chunk_id="collections-001",
                title="Collection Agencies",
                section="Agency handling",
                source="https://www.epaylater.in/Collection_Agencies.pdf",
                text=(
                    "Collections interactions should follow authorized agency practices "
                    "and avoid disclosure beyond what is necessary for collection activity."
                ),
            ),
        ]

    def search(self, query: str, limit: int = 4) -> list[PolicyChunk]:
        terms = {word.lower().strip("?,.") for word in query.split() if len(word) > 3}
        ranked = sorted(
            self._chunks,
            key=lambda chunk: sum(term in chunk.text.lower() or term in chunk.title.lower() for term in terms),
            reverse=True,
        )
        return ranked[:limit]

