from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Money = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=2, allow_inf_nan=False)]
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False)]


def financial_year(value: date) -> str:
    start = value.year if value.month >= 4 else value.year - 1
    return f"{start}-{start + 1}"


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0, le=1_000_000, strict=True)
    unit_price: Money
    tax_rate: Rate
    hsn_code: str | None = Field(default=None, max_length=20, pattern=r"^[0-9]{4,8}$")

    @field_validator("unit_price", "tax_rate")
    @classmethod
    def canonical_decimal(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))


class PdfInvoiceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    invoice_number: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9/-]*$")
    invoice_date: date
    customer_name: str = Field(min_length=1, max_length=255)
    customer_gstin: str | None = Field(default=None, pattern=r"^[0-9]{2}[A-Z0-9]{13}$")
    customer_address: str | None = Field(default=None, max_length=500)
    customer_phone: str | None = Field(default=None, max_length=50)
    subtotal: Money
    cgst: Money = Decimal("0")
    sgst: Money = Decimal("0")
    igst: Money = Decimal("0")
    round_off: Decimal = Field(default=Decimal("0"), gt=-1, lt=1, decimal_places=2, allow_inf_nan=False)
    total_amount: Money
    notes: str | None = Field(default=None, max_length=2000)
    source: Literal["uploaded", "generated"] = "uploaded"
    line_items: list[InvoiceLine] | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("invoice_number", "customer_gstin", mode="before")
    @classmethod
    def normalize_identifier(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("subtotal", "cgst", "sgst", "igst", "round_off", "total_amount")
    @classmethod
    def canonical_money(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01")) if value else Decimal("0.00")

    @model_validator(mode="after")
    def reconcile(self):
        if self.igst and (self.cgst or self.sgst):
            raise ValueError("Use IGST or CGST/SGST, not both")
        if self.subtotal + self.cgst + self.sgst + self.igst + self.round_off != self.total_amount:
            raise ValueError("Taxable amount + GST + round-off must equal the invoice total")
        if self.line_items is not None:
            taxable = sum(line.quantity * line.unit_price for line in self.line_items)
            tax = sum(
                (line.quantity * line.unit_price * line.tax_rate / 100).quantize(Decimal("0.01"))
                for line in self.line_items
            )
            if taxable != self.subtotal or tax != self.cgst + self.sgst + self.igst:
                raise ValueError("Line amounts and per-item taxes must match the invoice totals")
        if self.source == "generated" and not self.line_items:
            raise ValueError("Generated invoices must include their line-item snapshots")
        return self


class PdfInvoiceResponse(PdfInvoiceMetadata):
    model_config = ConfigDict(from_attributes=True)

    id: int
    financial_year: str
    original_filename: str
    pdf_sha256: str
    upload_status: Literal["pending", "ready"]
    created_at: datetime
    created_by_id: int


class PdfInvoicePage(BaseModel):
    items: list[PdfInvoiceResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
