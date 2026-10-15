from __future__ import annotations

from sqlalchemy.orm import Session

from bfs_bot.database import SessionLocal, create_schema
from bfs_bot.demo_data.generator import (
    FILLER_CUSTOMER_COUNT,
    DemoDataset,
    generate_demo,
)
from bfs_bot.models import (
    Customer,
    DiscountCode,
    Invoice,
    Payment,
    PolicyChunk,
)


def persist_demo_dataset(session: Session, dataset: DemoDataset) -> None:
    _clear_demo_tables(session)
    for row in dataset.customers:
        session.add(
            Customer(
                customer_id=row.customer_id,
                name=row.name,
                signup_date=row.signup_date,
                plan=row.plan,
                status=row.status,
            )
        )
    session.flush()
    for row in dataset.discount_codes:
        session.add(
            DiscountCode(
                discount_code=row.discount_code,
                policy_id=row.policy_id,
            )
        )
    for row in dataset.invoices:
        session.add(
            Invoice(
                invoice_id=row.invoice_id,
                customer_id=row.customer_id,
                invoice_date=row.invoice_date,
                due_date=row.due_date,
                gross=row.gross,
                discount_code=row.discount_code,
                discount_amt=row.discount_amt,
                late_fee=row.late_fee,
                net=row.net,
            )
        )
    session.flush()
    for row in dataset.payments:
        session.add(
            Payment(
                payment_id=row.payment_id,
                invoice_id=row.invoice_id,
                paid_on=row.paid_on,
                amount=row.amount,
            )
        )
    for row in dataset.policy_chunks:
        session.add(
            PolicyChunk(
                doc_id=row.doc_id,
                version=row.version,
                section=row.section,
                effective_from=row.effective_from,
                effective_to=row.effective_to,
                text=row.text,
                embedding=row.embedding,
                is_injection_probe=row.is_injection_probe,
            )
        )
    session.commit()


def _clear_demo_tables(session: Session) -> None:
    session.query(Payment).delete()
    session.query(Invoice).delete()
    session.query(DiscountCode).delete()
    session.query(PolicyChunk).delete()
    session.query(Customer).delete()
    session.flush()


def main() -> None:
    create_schema()
    dataset = generate_demo(seed=42)
    with SessionLocal() as session:
        persist_demo_dataset(session, dataset)
    print(
        "Seeded hybrid RAG payments demo: "
        f"{len(dataset.customers)} customers, "
        f"{len(dataset.invoices)} invoices, "
        f"{len(dataset.policy_chunks)} policy chunks "
        f"({FILLER_CUSTOMER_COUNT} filler + 7 named customers)."
    )


if __name__ == "__main__":
    main()
