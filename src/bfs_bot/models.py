from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - local tests may not have pgvector installed
    Vector = None


class Base(DeclarativeBase):
    pass


def embedding_column() -> Any:
    if Vector is None:
        return mapped_column(JSON, nullable=False)
    return mapped_column(Vector(384), nullable=False)


class SMECustomer(Base):
    __tablename__ = "sme_customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(160))
    contact_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(32))
    pan: Mapped[str] = mapped_column(String(16))
    gstin: Mapped[str] = mapped_column(String(24))
    registered_address: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(80))
    risk_tier: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    credit_account: Mapped["CreditAccount"] = relationship(back_populates="customer", uselist=False)
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer")
    support_cases: Mapped[list["SupportCase"]] = relationship(back_populates="customer")


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("sme_customers.id"), index=True)
    lender_name: Mapped[str] = mapped_column(String(120))
    account_status: Mapped[str] = mapped_column(String(32))
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    utilized_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    available_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    overdue_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    next_due_date: Mapped[date] = mapped_column(Date)

    customer: Mapped[SMECustomer] = relationship(back_populates="credit_account")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("sme_customers.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True)
    supplier_name: Mapped[str] = mapped_column(String(160))
    invoice_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    due_date: Mapped[date] = mapped_column(Date)
    repayment_status: Mapped[str] = mapped_column(String(32))

    customer: Mapped[SMECustomer] = relationship(back_populates="transactions")


class SupportCase(Base):
    __tablename__ = "support_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("sme_customers.id"), index=True)
    case_number: Mapped[str] = mapped_column(String(40), unique=True)
    category: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    opened_at: Mapped[datetime] = mapped_column(DateTime)
    summary: Mapped[str] = mapped_column(Text)

    customer: Mapped[SMECustomer] = relationship(back_populates="support_cases")


class PolicyDocumentChunk(Base):
    __tablename__ = "policy_document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    section: Mapped[str] = mapped_column(String(180))
    source_url: Mapped[str] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = embedding_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentAuditEvent(Base):
    __tablename__ = "agent_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[str] = mapped_column(String(64), index=True)
    agent: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

