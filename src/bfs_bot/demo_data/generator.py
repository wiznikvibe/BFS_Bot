"""Seeded synthetic demo dataset for Hybrid RAG Payments POC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import random
from typing import Literal

from bfs_bot.demo_data.policies import PolicyChunkDraft, build_policy_chunk_drafts
from bfs_bot.embeddings import hash_embedding

FILLER_CUSTOMER_COUNT = 200
INVOICE_COUNT_MIN = 1000
INVOICE_COUNT_MAX = 2000

Plan = Literal["monthly", "annual"]

TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class CustomerRow:
    customer_id: str
    name: str
    signup_date: date
    plan: Plan
    status: str


@dataclass(frozen=True)
class InvoiceRow:
    invoice_id: str
    customer_id: str
    invoice_date: date
    due_date: date
    gross: Decimal
    discount_code: str | None
    discount_amt: Decimal
    late_fee: Decimal
    net: Decimal


@dataclass(frozen=True)
class PaymentRow:
    payment_id: str
    invoice_id: str
    paid_on: date
    amount: Decimal


@dataclass(frozen=True)
class DiscountCodeRow:
    discount_code: str
    policy_id: str


@dataclass(frozen=True)
class PolicyChunkRow:
    doc_id: str
    version: str
    section: str
    effective_from: date
    effective_to: date | None
    text: str
    embedding: list[float]
    is_injection_probe: bool


@dataclass(frozen=True)
class DemoDataset:
    customers: list[CustomerRow]
    invoices: list[InvoiceRow]
    payments: list[PaymentRow]
    discount_codes: list[DiscountCodeRow]
    policy_chunks: list[PolicyChunkRow]


NAMED_CUSTOMERS: list[CustomerRow] = [
    CustomerRow("C001", "Asha Verma", date(2026, 1, 15), "monthly", "active"),
    CustomerRow("C002", "Ben Carter", date(2025, 8, 10), "monthly", "active"),
    CustomerRow("C003", "Carla Gomez", date(2025, 7, 30), "monthly", "active"),
    CustomerRow("C004", "Dev Patel", date(2025, 4, 1), "monthly", "active"),
    CustomerRow("C005", "Elena Rossi", date(2025, 6, 10), "annual", "active"),
    CustomerRow("C006", "Farid Khan", date(2025, 9, 1), "monthly", "active"),
    CustomerRow("C007", "Gita Nair", date(2026, 3, 5), "monthly", "active"),
]

NAMED_INVOICES: list[InvoiceRow] = [
    InvoiceRow(
        "INV-1001",
        "C001",
        date(2026, 9, 15),
        date(2026, 9, 15),
        Decimal("100.00"),
        None,
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    ),
    InvoiceRow(
        "INV-1002",
        "C002",
        date(2026, 9, 10),
        date(2026, 9, 10),
        Decimal("100.00"),
        "LOYALTY10",
        Decimal("10.00"),
        Decimal("0.00"),
        Decimal("90.00"),
    ),
    InvoiceRow(
        "INV-1003",
        "C003",
        date(2026, 9, 30),
        date(2026, 9, 30),
        Decimal("100.00"),
        None,
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    ),
    InvoiceRow(
        "INV-1004",
        "C004",
        date(2025, 11, 5),
        date(2025, 11, 5),
        Decimal("100.00"),
        "LOYALTY5",
        Decimal("5.00"),
        Decimal("0.00"),
        Decimal("95.00"),
    ),
    InvoiceRow(
        "INV-1005",
        "C005",
        date(2026, 9, 1),
        date(2026, 9, 1),
        Decimal("1200.00"),
        "ANNUAL15",
        Decimal("180.00"),
        Decimal("0.00"),
        Decimal("1020.00"),
    ),
    InvoiceRow(
        "INV-1006",
        "C006",
        date(2026, 9, 1),
        date(2026, 9, 1),
        Decimal("200.00"),
        None,
        Decimal("0.00"),
        Decimal("4.00"),
        Decimal("204.00"),
    ),
    InvoiceRow(
        "INV-1007",
        "C007",
        date(2026, 9, 20),
        date(2026, 9, 20),
        Decimal("100.00"),
        None,
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    ),
]

NAMED_PAYMENT_OVERRIDES: dict[str, tuple[date, Decimal]] = {
    "INV-1006": (date(2026, 9, 5), Decimal("204.00")),
    "INV-1007": (date(2026, 9, 20), Decimal("100.00")),
}

DISCOUNT_CODES: list[DiscountCodeRow] = [
    DiscountCodeRow("LOYALTY10", "loyalty-discount-policy"),
    DiscountCodeRow("LOYALTY5", "loyalty-discount-policy"),
    DiscountCodeRow("ANNUAL15", "annual-plan-discount-policy"),
]

FILLER_FIRST_NAMES = [
    "Aarav",
    "Isha",
    "Rohan",
    "Meera",
    "Vikram",
    "Ananya",
    "Kabir",
    "Priya",
    "Neha",
    "Arjun",
]
FILLER_LAST_NAMES = [
    "Sharma",
    "Iyer",
    "Menon",
    "Das",
    "Kapoor",
    "Reddy",
    "Singh",
    "Bose",
    "Chopra",
    "Malhotra",
]


def generate_demo(seed: int = 42, as_of: date = date(2026, 10, 15)) -> DemoDataset:
    rng = random.Random(seed)
    customers = list(NAMED_CUSTOMERS) + _generate_filler_customers(rng, FILLER_CUSTOMER_COUNT)

    target_invoices = rng.randint(INVOICE_COUNT_MIN, INVOICE_COUNT_MAX)
    filler_invoice_target = max(0, target_invoices - len(NAMED_INVOICES))
    filler_invoices = _generate_filler_invoices(rng, customers, filler_invoice_target, as_of)

    invoices = list(NAMED_INVOICES) + filler_invoices
    payments = _payments_for_invoices(invoices)
    policy_chunks = _policy_chunks_with_embeddings(build_policy_chunk_drafts())

    return DemoDataset(
        customers=customers,
        invoices=invoices,
        payments=payments,
        discount_codes=list(DISCOUNT_CODES),
        policy_chunks=policy_chunks,
    )


def _generate_filler_customers(rng: random.Random, count: int) -> list[CustomerRow]:
    rows: list[CustomerRow] = []
    for index in range(count):
        serial = 8 + index
        signup = date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))
        plan: Plan = "annual" if rng.random() < 0.15 else "monthly"
        first = rng.choice(FILLER_FIRST_NAMES)
        last = rng.choice(FILLER_LAST_NAMES)
        rows.append(
            CustomerRow(
                customer_id=f"C{serial:03d}",
                name=f"{first} {last}",
                signup_date=signup,
                plan=plan,
                status="active",
            )
        )
    return rows


def _generate_filler_invoices(
    rng: random.Random,
    customers: list[CustomerRow],
    count: int,
    as_of: date,
) -> list[InvoiceRow]:
    filler_customers = [c for c in customers if c.customer_id not in {n.customer_id for n in NAMED_CUSTOMERS}]
    rows: list[InvoiceRow] = []
    next_serial = 1008
    eligible = [
        c
        for c in filler_customers
        if c.signup_date + timedelta(days=31) <= as_of
    ]
    if not eligible:
        eligible = list(filler_customers)
    attempts = 0
    while len(rows) < count and attempts < count * 20:
        attempts += 1
        customer = rng.choice(eligible)
        earliest = customer.signup_date + timedelta(days=31)
        if earliest > as_of:
            continue
        span_days = (as_of - earliest).days
        invoice_date = earliest + timedelta(days=rng.randint(0, span_days))
        due_date = invoice_date
        gross = _gross_for_plan(customer.plan, rng)
        discount_code, discount_amt = _eligible_discount(customer, invoice_date, gross)
        days_late = rng.randint(0, 14)
        paid_on = due_date + timedelta(days=days_late)
        late_fee = _late_fee(gross, due_date, paid_on)
        net = (gross - discount_amt + late_fee).quantize(TWOPLACES, ROUND_HALF_UP)
        rows.append(
            InvoiceRow(
                invoice_id=f"INV-{next_serial}",
                customer_id=customer.customer_id,
                invoice_date=invoice_date,
                due_date=due_date,
                gross=gross,
                discount_code=discount_code,
                discount_amt=discount_amt,
                late_fee=late_fee,
                net=net,
            )
        )
        next_serial += 1
    return rows


def _gross_for_plan(plan: Plan, rng: random.Random) -> Decimal:
    if plan == "annual":
        base = Decimal(rng.randint(1000, 1500))
    else:
        base = Decimal(rng.randint(50, 250))
    return base.quantize(TWOPLACES, ROUND_HALF_UP)


def _months_membership(signup: date, on_date: date) -> int:
    months = (on_date.year - signup.year) * 12 + (on_date.month - signup.month)
    if on_date.day < signup.day:
        months -= 1
    return max(0, months)


def _eligible_discount(
    customer: CustomerRow,
    invoice_date: date,
    gross: Decimal,
) -> tuple[str | None, Decimal]:
    loyalty_code, loyalty_rate = _loyalty_for_date(customer, invoice_date)
    annual_rate = Decimal("0.15") if customer.plan == "annual" else Decimal("0")
    loyalty_amt = (gross * loyalty_rate).quantize(TWOPLACES, ROUND_HALF_UP)
    annual_amt = (gross * annual_rate).quantize(TWOPLACES, ROUND_HALF_UP)
    if annual_amt > loyalty_amt and annual_amt > 0:
        return "ANNUAL15", annual_amt
    if loyalty_amt > 0 and loyalty_code:
        return loyalty_code, loyalty_amt
    return None, Decimal("0.00")


def _loyalty_for_date(customer: CustomerRow, invoice_date: date) -> tuple[str | None, Decimal]:
    months = _months_membership(customer.signup_date, invoice_date)
    if invoice_date >= date(2026, 1, 1):
        if months >= 12:
            return "LOYALTY10", Decimal("0.10")
        return None, Decimal("0")
    if months >= 6:
        return "LOYALTY5", Decimal("0.05")
    return None, Decimal("0")


def _late_fee(gross: Decimal, due_date: date, paid_on: date) -> Decimal:
    grace_end = due_date + timedelta(days=7)
    if paid_on <= grace_end:
        return Decimal("0.00")
    fee = (gross * Decimal("0.02")).quantize(TWOPLACES, ROUND_HALF_UP)
    return fee


def _payments_for_invoices(invoices: list[InvoiceRow]) -> list[PaymentRow]:
    payments: list[PaymentRow] = []
    for invoice in invoices:
        if invoice.invoice_id in NAMED_PAYMENT_OVERRIDES:
            paid_on, amount = NAMED_PAYMENT_OVERRIDES[invoice.invoice_id]
        else:
            paid_on = invoice.due_date
            amount = invoice.net
        serial = invoice.invoice_id.replace("INV-", "")
        payments.append(
            PaymentRow(
                payment_id=f"PAY-{serial}",
                invoice_id=invoice.invoice_id,
                paid_on=paid_on,
                amount=amount,
            )
        )
    return payments


def _policy_chunks_with_embeddings(drafts: list[PolicyChunkDraft]) -> list[PolicyChunkRow]:
    rows: list[PolicyChunkRow] = []
    for draft in drafts:
        embedding = hash_embedding(draft.text) if not draft.is_injection_probe else [0.0] * 384
        rows.append(
            PolicyChunkRow(
                doc_id=draft.doc_id,
                version=draft.version,
                section=draft.section,
                effective_from=draft.effective_from,
                effective_to=draft.effective_to,
                text=draft.text,
                embedding=embedding,
                is_injection_probe=draft.is_injection_probe,
            )
        )
    return rows
