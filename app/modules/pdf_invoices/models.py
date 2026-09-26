from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseModel


class PdfInvoice(BaseModel):
    """An archived invoice, not a stock movement or receivable."""

    __tablename__ = "pdf_invoices"
    __table_args__ = (
        UniqueConstraint("financial_year", "invoice_number", name="uq_pdf_invoice_number_year"),
        UniqueConstraint("pdf_sha256", name="uq_pdf_invoice_sha256"),
    )

    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    financial_year: Mapped[str] = mapped_column(String(9), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_gstin: Mapped[str | None] = mapped_column(String(15))
    customer_address: Mapped[str | None] = mapped_column(String(500))
    customer_phone: Mapped[str | None] = mapped_column(String(50))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    cgst: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    sgst: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    igst: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    round_off: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    line_items: Mapped[list | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
