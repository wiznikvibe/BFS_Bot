from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def embedding_column() -> Any:
    """JSON list of floats; ranked in Python via cosine_similarity."""
    return mapped_column(
        JSON,
        nullable=False,
        comment="Embedding vector stored as JSON for portable retrieval ranking.",
    )


class Customer(Base):
    """Membership identity: plan type and tenure for billing-policy questions."""

    __tablename__ = "customers"
    __table_args__ = {"comment": "Demo customers; membership length and plan drive discount eligibility."}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        comment="External customer identifier (e.g. C001).",
    )
    name: Mapped[str] = mapped_column(String(160), comment="Customer display name.")
    signup_date: Mapped[date] = mapped_column(
        Date, comment="Date membership started; used for loyalty tenure."
    )
    plan: Mapped[str] = mapped_column(
        String(32), comment="Billing plan: monthly or annual."
    )
    status: Mapped[str] = mapped_column(
        String(32), comment="Account status (e.g. active)."
    )

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")


class Invoice(Base):
    """Billed amount with applied discount codes and late fees."""

    __tablename__ = "invoices"
    __table_args__ = {"comment": "Invoices billed to customers; links discounts and fees to line items."}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        index=True,
        comment="External invoice identifier (e.g. INV-1001).",
    )
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.customer_id"),
        index=True,
        comment="Customer who was billed.",
    )
    invoice_date: Mapped[date] = mapped_column(Date, comment="Date the invoice was issued.")
    due_date: Mapped[date] = mapped_column(Date, comment="Payment due date.")
    gross: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), comment="Pre-discount invoice amount."
    )
    discount_code: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="Promotional or loyalty code applied, if any.",
    )
    discount_amt: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), comment="Discount amount subtracted from gross."
    )
    late_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), comment="Late payment fee applied to this invoice."
    )
    net: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), comment="Amount due after discounts and fees."
    )

    customer: Mapped[Customer] = relationship(back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")


class Payment(Base):
    """Actual payment against an invoice."""

    __tablename__ = "payments"
    __table_args__ = {"comment": "Payments received; timing vs due date drives late-fee scenarios."}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        index=True,
        comment="External payment identifier.",
    )
    invoice_id: Mapped[str] = mapped_column(
        ForeignKey("invoices.invoice_id"),
        index=True,
        comment="Invoice this payment settles.",
    )
    paid_on: Mapped[date] = mapped_column(Date, comment="Date payment was received.")
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), comment="Amount paid."
    )

    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class DiscountCode(Base):
    """Maps a billing code to the policy document that defines it."""

    __tablename__ = "discount_codes"
    __table_args__ = {
        "comment": "Discount codes link applied invoice codes to policy doc_id for hybrid Q&A."
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discount_code: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        index=True,
        comment="Code applied on invoices (e.g. LOYALTY10).",
    )
    policy_id: Mapped[str] = mapped_column(
        String(80),
        comment="Policy document id (doc_id) that defines this code.",
    )


class PolicyChunk(Base):
    """Vector-indexed policy text with version and effective dating."""

    __tablename__ = "policy_chunks"
    __table_args__ = {
        "comment": "Chunked policy documents for RAG; metadata supports version and date filtering."
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String(80),
        index=True,
        comment="Logical policy document identifier.",
    )
    version: Mapped[str] = mapped_column(
        String(16), comment="Policy version label (e.g. v2, v3)."
    )
    section: Mapped[str] = mapped_column(
        String(180), comment="Section heading within the document."
    )
    effective_from: Mapped[date] = mapped_column(
        Date, comment="First date this chunk is in force."
    )
    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Last date in force, inclusive; null if still current.",
    )
    text: Mapped[str] = mapped_column(Text, comment="Chunk body text for retrieval and citations.")
    embedding: Mapped[Any] = embedding_column()
    is_injection_probe: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="True for test-only prompt-injection probe chunks.",
    )


class AuditEvent(Base):
    """Supervisor and agent audit trail for demo observability."""

    __tablename__ = "audit_events"
    __table_args__ = {"comment": "Query routing, tool use, and outcomes for compliance demo."}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[str] = mapped_column(
        String(64), index=True, comment="Correlates events for one user question."
    )
    agent: Mapped[str] = mapped_column(
        String(80), comment="Component that emitted the event (supervisor, structured, policy)."
    )
    status: Mapped[str] = mapped_column(String(40), comment="Outcome or phase label.")
    detail: Mapped[str] = mapped_column(Text, comment="Human-readable or JSON detail payload.")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="Event timestamp."
    )
