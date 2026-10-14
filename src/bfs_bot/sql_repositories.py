from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bfs_bot.embeddings import cosine_similarity, hash_embedding
from bfs_bot.models import CreditAccount, PolicyDocumentChunk, SMECustomer
from bfs_bot.repositories import PolicyChunk


class SQLCustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_customer_by_id(self, customer_id: str) -> dict | None:
        customer = self.session.scalar(
            select(SMECustomer).where(SMECustomer.customer_id == customer_id.upper())
        )
        if not customer:
            return None

        account = self.session.scalar(
            select(CreditAccount).where(CreditAccount.customer_id == customer.id)
        )
        record = {
            "customer_id": customer.customer_id,
            "business_name": customer.business_name,
            "contact_name": customer.contact_name,
            "email": customer.email,
            "phone": customer.phone,
            "pan": customer.pan,
            "gstin": customer.gstin,
            "registered_address": customer.registered_address,
            "industry": customer.industry,
            "region": customer.region,
            "risk_tier": customer.risk_tier,
        }
        if account:
            record.update(
                {
                    "lender_name": account.lender_name,
                    "account_status": account.account_status,
                    "credit_limit": float(account.credit_limit),
                    "utilized_amount": float(account.utilized_amount),
                    "available_limit": float(account.available_limit),
                    "overdue_amount": float(account.overdue_amount),
                    "next_due_date": account.next_due_date.isoformat(),
                }
            )
        return record


class SQLPolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, limit: int = 4) -> list[PolicyChunk]:
        query_embedding = hash_embedding(query)
        rows = self.session.scalars(select(PolicyDocumentChunk)).all()
        ranked = sorted(
            rows,
            key=lambda row: cosine_similarity(query_embedding, list(row.embedding)),
            reverse=True,
        )
        return [
            PolicyChunk(
                chunk_id=row.chunk_id,
                title=row.title,
                section=row.section,
                source=row.source_url,
                text=row.text,
            )
            for row in ranked[:limit]
        ]

