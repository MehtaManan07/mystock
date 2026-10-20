from sqlalchemy import String, cast, func, literal, null, select, union_all
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from app.modules.pdf_invoices.models import PdfInvoice
from app.modules.transactions.models import Transaction
from .models import Contact
from .schemas import ContactBill, ContactBillPage


class ContactBillsService:
    @staticmethod
    async def list_bills(contact_id: int, page: int, page_size: int) -> ContactBillPage:
        def read(db: Session):
            contact = db.get(Contact, contact_id)
            if contact is None or contact.deleted_at is not None:
                raise NotFoundError("Contact", contact_id)

            transactions = select(
                literal("transaction").label("source"),
                Transaction.id.label("id"),
                Transaction.transaction_number.label("number"),
                Transaction.transaction_date.label("date"),
                Transaction.total_amount.label("total_amount"),
                cast(Transaction.type, String).label("transaction_type"),
                cast(Transaction.payment_status, String).label("payment_status"),
                cast(null(), String).label("upload_status"),
                Transaction.created_at.label("created_at"),
            ).where(Transaction.contact_id == contact_id, Transaction.deleted_at.is_(None))
            pdfs = select(
                literal("pdf_invoice").label("source"),
                PdfInvoice.id.label("id"),
                PdfInvoice.invoice_number.label("number"),
                PdfInvoice.invoice_date.label("date"),
                PdfInvoice.total_amount.label("total_amount"),
                cast(null(), String).label("transaction_type"),
                cast(null(), String).label("payment_status"),
                PdfInvoice.upload_status.label("upload_status"),
                PdfInvoice.created_at.label("created_at"),
            ).where(PdfInvoice.deleted_at.is_(None), PdfInvoice.customer_id == contact_id)

            # Paginate the combined history, not separate pages from each register.
            bills = union_all(transactions, pdfs).subquery("contact_bills")
            total = db.scalar(select(func.count()).select_from(bills)) or 0
            rows = db.execute(select(bills).order_by(
                bills.c.date.desc(), bills.c.created_at.desc(),
                bills.c.source.asc(), bills.c.id.desc(),
            ).offset((page - 1) * page_size).limit(page_size)).mappings().all()
            return ContactBillPage(
                items=[ContactBill.model_validate(row) for row in rows],
                total=total, page=page, page_size=page_size,
                has_more=page * page_size < total,
            )

        return await run_db(read)
