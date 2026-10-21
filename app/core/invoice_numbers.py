import re

from sqlalchemy import select, text, union_all
from sqlalchemy.orm import Session


def lock_sales_numbering(db: Session) -> None:
    # Shared by sales, PDF reservations, and historical imports; held until commit/rollback.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(1262698830)"))
    elif db.get_bind().dialect.name != "sqlite":
        raise RuntimeError("Sales numbering requires PostgreSQL (SQLite is supported for offline tests)")


def next_sale_number(db: Session) -> str:
    from app.modules.pdf_invoices.models import PdfInvoice, PdfInvoiceNumberReservation
    from app.modules.transactions.models import Transaction

    lock_sales_numbering(db)
    numbers = db.scalars(union_all(
        select(Transaction.transaction_number),
        select(PdfInvoice.invoice_number),
        select(PdfInvoiceNumberReservation.invoice_number),
    )).all()
    highest = max(
        (int(match.group(1)) for number in numbers
         if (match := re.fullmatch(r"SALE-(\d+)", number, flags=re.IGNORECASE))),
        default=0,
    )
    return f"SALE-{highest + 1:04d}"
