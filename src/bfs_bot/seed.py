from __future__ import annotations

from datetime import date, datetime, timedelta
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from bfs_bot.config import settings
from bfs_bot.database import SessionLocal, create_schema
from bfs_bot.models import CreditAccount, SMECustomer, SupportCase, Transaction

try:
    from faker import Faker
except Exception:  # pragma: no cover - production dependency, fallback for lean envs
    Faker = None


INDUSTRIES = [
    "Packaging and wholesale supplies",
    "Restaurant supplies",
    "Electronics distribution",
    "Textile trading",
    "Pharmacy retail",
    "Automotive spares",
]
REGIONS = ["Mumbai", "Pune", "Bengaluru", "Delhi NCR", "Hyderabad", "Chennai"]
RISK_TIERS = ["A", "B", "C"]


def seed_customers(session: Session, count: int) -> None:
    if session.scalar(select(SMECustomer).limit(1)):
        return

    fake = Faker("en_IN") if Faker else None
    rng = random.Random(42)
    for index in range(count):
        serial = 10000 + index
        customer = SMECustomer(
            customer_id=f"SME-{serial}",
            business_name=_company(fake, serial),
            contact_name=_name(fake, serial),
            email=f"owner{serial}@example-sme.test",
            phone=f"+91 9{rng.randint(1000, 9999)} {rng.randint(10000, 99999)}",
            pan=f"ABCDE{serial % 9000 + 1000}F",
            gstin=f"27ABCDE{serial % 9000 + 1000}F1Z5",
            registered_address=_address(fake, serial),
            industry=rng.choice(INDUSTRIES),
            region=rng.choice(REGIONS),
            risk_tier=rng.choice(RISK_TIERS),
        )
        session.add(customer)
        session.flush()

        credit_limit = rng.choice([100000, 150000, 250000, 500000, 750000])
        utilized = rng.randint(0, int(credit_limit * 0.85 / 500)) * 500
        overdue = 0 if rng.random() > 0.2 else rng.randint(1, 20) * 1000
        session.add(
            CreditAccount(
                customer_id=customer.id,
                lender_name="Partner NBFC Demo",
                account_status="active" if overdue == 0 else "watchlist",
                credit_limit=credit_limit,
                utilized_amount=utilized,
                available_limit=credit_limit - utilized,
                overdue_amount=overdue,
                next_due_date=date.today() + timedelta(days=rng.randint(3, 45)),
            )
        )
        for txn_index in range(3):
            amount = rng.randint(10, 120) * 1000
            session.add(
                Transaction(
                    customer_id=customer.id,
                    invoice_number=f"INV-{serial}-{txn_index + 1}",
                    supplier_name=f"Supplier {rng.choice(['Alpha', 'Nava', 'Metro', 'Prime'])}",
                    invoice_amount=amount,
                    due_date=date.today() + timedelta(days=rng.randint(7, 60)),
                    repayment_status=rng.choice(["pending", "paid", "partially_paid"]),
                )
            )
        if rng.random() < 0.35:
            session.add(
                SupportCase(
                    customer_id=customer.id,
                    case_number=f"CASE-{serial}",
                    category=rng.choice(["grievance", "repayment", "limit_review"]),
                    status=rng.choice(["open", "in_review", "resolved"]),
                    opened_at=datetime.utcnow() - timedelta(days=rng.randint(1, 20)),
                    summary="Dummy support case for PoC agent routing.",
                )
            )
    session.commit()


def _company(fake: object | None, serial: int) -> str:
    if fake:
        return fake.company()
    return f"Demo SME Trading {serial}"


def _name(fake: object | None, serial: int) -> str:
    if fake:
        return fake.name()
    return f"Owner {serial}"


def _address(fake: object | None, serial: int) -> str:
    if fake:
        return fake.address().replace("\n", ", ")
    return f"{serial % 200 + 1} Market Road, Pune"


def main() -> None:
    create_schema()
    with SessionLocal() as session:
        seed_customers(session, settings.seed_customer_count)
    print(f"Seeded dummy customer data if database was empty ({settings.seed_customer_count} target records).")


if __name__ == "__main__":
    main()

