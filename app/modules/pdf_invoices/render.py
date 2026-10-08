from datetime import date
from decimal import Decimal, ROUND_CEILING
from types import SimpleNamespace
from typing import Literal
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field

from app.modules.transactions.invoice_generator import InvoiceGenerator
from app.modules.transactions.models import ProductDetailsDisplayMode, TaxType
from .schemas import InvoiceLine, Money, PdfInvoiceMetadata


class GeneratePdfInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str
    show_invoice_number: bool = Field(default=True, strict=True)
    invoice_date: date
    customer_name: str
    customer_gstin: str | None = None
    customer_address: str | None = None
    customer_phone: str | None = None
    tax_type: Literal["igst", "cgst_sgst"]
    line_items: list[InvoiceLine] = Field(min_length=1, max_length=200)
    total_amount: Money | None = None
    notes: str | None = None


def render_invoice(spec: GeneratePdfInvoice, seller: SimpleNamespace) -> tuple[PdfInvoiceMetadata, bytes]:
    items = []
    buckets: dict[Decimal, Decimal] = {}
    subtotal = Decimal("0.00")
    for line in spec.line_items:
        taxable = line.quantity * line.unit_price
        tax = (taxable * line.tax_rate / 100).quantize(Decimal("0.01"))
        subtotal += taxable
        buckets[line.tax_rate] = buckets.get(line.tax_rate, Decimal("0.00")) + tax
        items.append(SimpleNamespace(
            product=SimpleNamespace(name=escape(line.name), hsn_code=line.hsn_code),
            quantity=line.quantity, unit_price=line.unit_price,
            tax_rate=line.tax_rate, tax_amount=tax,
        ))
    tax = sum(buckets.values(), Decimal("0.00"))
    cgst = (
        sum((value / 2).quantize(Decimal("0.01")) for value in buckets.values())
        if spec.tax_type == "cgst_sgst" else Decimal("0.00")
    )
    sgst = tax - cgst if spec.tax_type == "cgst_sgst" else Decimal("0.00")
    target = spec.total_amount
    if target is None:
        target = (subtotal + tax).to_integral_value(rounding=ROUND_CEILING)
    metadata = PdfInvoiceMetadata(
        **spec.model_dump(exclude={"tax_type", "total_amount", "show_invoice_number"}),
        subtotal=subtotal, cgst=cgst, sgst=sgst,
        igst=tax if spec.tax_type == "igst" else Decimal("0.00"),
        round_off=target - subtotal - tax, total_amount=target, source="generated",
    )
    transaction = SimpleNamespace(
        transaction_number=metadata.invoice_number,
        transaction_date=metadata.invoice_date,
        contact=SimpleNamespace(
            name=metadata.customer_name, gstin=metadata.customer_gstin,
            address=metadata.customer_address, phone=metadata.customer_phone,
        ),
        product_details_display_mode=ProductDetailsDisplayMode.product_name,
        tax_type=TaxType(spec.tax_type),
        items=items, subtotal=subtotal, tax_amount=tax,
        total_amount=target, discount_amount=Decimal("0.00"),
    )
    return metadata, InvoiceGenerator.generate_invoice_pdf(
        transaction, seller, None, show_invoice_number=spec.show_invoice_number,
    )
