"""TDD: payments + policy ORM schema (Task 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from bfs_bot.embeddings import hash_embedding
from bfs_bot.models import (
    AuditEvent,
    Base,
    Customer,
    DiscountCode,
    Invoice,
    Payment,
    PolicyChunk,
)

EXPECTED_TABLES = frozenset(
    {
        "customers",
        "invoices",
        "payments",
        "discount_codes",
        "policy_chunks",
        "audit_events",
    }
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as sess:
        yield sess


def test_all_payments_tables_created(session: Session) -> None:
    names = set(inspect(session.bind).get_table_names())
    assert EXPECTED_TABLES <= names


def test_table_and_column_comments_defined() -> None:
    assert Customer.__table__.comment
    assert Invoice.__table__.comment
    assert Payment.__table__.comment
    assert DiscountCode.__table__.comment
    assert PolicyChunk.__table__.comment
    assert AuditEvent.__table__.comment

    assert Customer.customer_id.comment
    assert Invoice.invoice_id.comment
    assert PolicyChunk.embedding.comment or PolicyChunk.text.comment


def test_insert_named_demo_customer_and_invoice(session: Session) -> None:
    session.add(
        Customer(
            customer_id="C001",
            name="Asha Verma",
            signup_date=date(2026, 1, 15),
            plan="monthly",
            status="active",
        )
    )
    session.add(
        Invoice(
            invoice_id="INV-1001",
            customer_id="C001",
            invoice_date=date(2026, 9, 15),
            due_date=date(2026, 9, 15),
            gross=Decimal("100.00"),
            discount_code=None,
            discount_amt=Decimal("0.00"),
            late_fee=Decimal("0.00"),
            net=Decimal("100.00"),
        )
    )
    session.commit()

    customer = session.scalar(select(Customer).where(Customer.customer_id == "C001"))
    assert customer is not None
    assert customer.name == "Asha Verma"

    invoice = session.scalar(select(Invoice).where(Invoice.invoice_id == "INV-1001"))
    assert invoice is not None
    assert invoice.customer_id == "C001"
    assert invoice.net == Decimal("100.00")


def test_policy_chunk_stores_json_embedding(session: Session) -> None:
    vector = hash_embedding("Late fee applies after grace period.")
    chunk = PolicyChunk(
        doc_id="late-fee-policy",
        version="v1",
        section="Grace period",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        text="A 2% late fee applies only after a 7-day grace period.",
        embedding=vector,
        is_injection_probe=False,
    )
    session.add(chunk)
    session.commit()

    loaded = session.scalar(select(PolicyChunk).where(PolicyChunk.doc_id == "late-fee-policy"))
    assert loaded is not None
    assert isinstance(loaded.embedding, list)
    assert len(loaded.embedding) == len(vector)
    assert loaded.is_injection_probe is False


def test_payment_and_discount_code_round_trip(session: Session) -> None:
    session.add(
        Customer(
            customer_id="C002",
            name="Ben Carter",
            signup_date=date(2025, 8, 10),
            plan="monthly",
            status="active",
        )
    )
    session.add(DiscountCode(discount_code="LOYALTY10", policy_id="loyalty-discount-policy"))
    session.add(
        Invoice(
            invoice_id="INV-1002",
            customer_id="C002",
            invoice_date=date(2026, 9, 10),
            due_date=date(2026, 9, 10),
            gross=Decimal("100.00"),
            discount_code="LOYALTY10",
            discount_amt=Decimal("10.00"),
            late_fee=Decimal("0.00"),
            net=Decimal("90.00"),
        )
    )
    session.add(
        Payment(
            payment_id="PAY-1002",
            invoice_id="INV-1002",
            paid_on=date(2026, 9, 10),
            amount=Decimal("90.00"),
        )
    )
    session.commit()

    payment = session.scalar(select(Payment).where(Payment.payment_id == "PAY-1002"))
    assert payment is not None
    assert payment.amount == Decimal("90.00")
