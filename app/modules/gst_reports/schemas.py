from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
import calendar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.pdf_invoices.schemas import Money, Rate


SourceKind = Literal["transaction", "pdf_invoice"]
Disposition = Literal["include", "cancelled", "not_issued", "duplicate"]
Treatment = Literal["taxable", "nil_rated", "exempt", "non_gst", "unknown"]
Quantity = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=3, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GstLine(StrictModel):
    line_key: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=255)
    quantity: Quantity
    unit_price: Money | None = None
    taxable_value: Money
    tax_rate: Rate | None = None
    tax_amount: Money | None = None
    hsn: str | None = Field(default=None, max_length=20)
    uqc: str | None = None
    treatment: Treatment = "unknown"


class RateTax(StrictModel):
    rate: Rate
    cgst: Money = Decimal("0")
    sgst: Money = Decimal("0")
    igst: Money = Decimal("0")


class GstDocument(StrictModel):
    number: str = Field(min_length=1, max_length=50)
    date: date
    kind: Literal["invoice", "credit_note", "debit_note"] = "invoice"
    seller_gstin: str | None = None
    customer_name: str = Field(min_length=1, max_length=255)
    customer_gstin: str | None = None
    place_of_supply: str | None = Field(default=None, pattern=r"^\d{2}$")
    invoice_type: Literal["regular", "sez_with_tax", "sez_without_tax", "deemed_export", "export"] | None = None
    reverse_charge: bool | None = None
    tax_type: Literal["igst", "cgst_sgst"]
    subtotal: Money
    tax_amount: Money
    cgst: Money | None = None
    sgst: Money | None = None
    igst: Money | None = None
    total_amount: Money
    discount_amount: Money = Decimal("0")
    round_off: Decimal = Field(default=Decimal("0"), allow_inf_nan=False, decimal_places=2)
    lines: list[GstLine] = Field(default_factory=list, max_length=2000)
    rate_taxes: list[RateTax] = Field(default_factory=list)
    original_invoice_number: str | None = Field(default=None, max_length=50)
    original_invoice_date: date | None = None
    original_invoice_value: Money | None = None
    series: str | None = Field(default=None, max_length=80)
    cess_amount: Money = Decimal("0")


class ReviewInput(StrictModel):
    expected_revision: int = Field(ge=0)
    expected_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document: GstDocument
    disposition: Disposition
    evidence: str = Field(min_length=10, max_length=4000)


class AdditionalDocumentInput(StrictModel):
    # A caller-generated stable identifier makes create retries safe.
    key: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    expected_revision: int = Field(ge=0)
    document: GstDocument
    disposition: Disposition = "include"
    evidence: str = Field(min_length=10, max_length=4000)


class ReportRequest(StrictModel):
    from_date: date
    to_date: date
    filing_frequency: Literal["monthly", "quarterly"]
    preceding_year_turnover_above_5cr: bool
    # Explicit attestations, not inferred from the absence of database records.
    sources_complete: bool = False
    no_iff_or_previously_filed_records: bool = False
    no_unsupported_supplies_or_amendments: bool = False
    cross_period_and_cancellations_reviewed: bool = False
    gstin_hsn_and_uqc_verified: bool = False
    document_series_complete: bool = False

    @model_validator(mode="after")
    def complete_period(self):
        if self.from_date.day != 1 or self.to_date < self.from_date:
            raise ValueError("Select a complete calendar month or GST quarter")
        months = 1 if self.filing_frequency == "monthly" else 3
        if months == 3 and self.from_date.month not in (1, 4, 7, 10):
            raise ValueError("Quarter must start in January, April, July or October")
        end_month = self.from_date.month + months - 1
        expected = date(self.from_date.year, end_month, calendar.monthrange(self.from_date.year, end_month)[1])
        if self.to_date != expected or self.to_date >= date.today():
            raise ValueError("Select one completed calendar month or quarter")
        if self.from_date < date(2025, 5, 1):
            raise ValueError("This workbook layout supports periods from May 2025 onwards")
        return self


class ExportRequest(StrictModel):
    report: ReportRequest
    expected_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Issue(StrictModel):
    code: str
    message: str
    source_key: str | None = None
    severity: Literal["blocker", "warning"] = "blocker"


class SourceView(StrictModel):
    source_key: str
    source_sha256: str
    revision: int
    verified: bool
    source_deleted: bool
    upload_ready: bool
    stale_review: bool
    disposition: Disposition
    evidence: str | None = None
    document: GstDocument
    source_document: GstDocument | None = None


class TaxTotals(StrictModel):
    taxable: Decimal = Decimal("0")
    nil_rated: Decimal = Decimal("0")
    exempt: Decimal = Decimal("0")
    non_gst: Decimal = Decimal("0")
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")


class Totals(TaxTotals):
    round_off: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class SalesGroup(TaxTotals):
    gstin: str | None
    invoice_type: str | None
    place_of_supply: str | None
    document_kind: str
    treatment: Treatment
    rate: Decimal | None
    source_keys: list[str] = Field(default_factory=list)


class Report(StrictModel):
    schema_version: str = "gstr1-offline-may2025-v1"
    request: ReportRequest
    seller_gstin: str | None
    documents: list[SourceView]
    issues: list[Issue]
    groups: list[SalesGroup]
    totals: Totals
    excluded_source_keys: list[str]
    source_invoice_total: Decimal
    included_document_total: Decimal
    excluded_document_total: Decimal
    source_reconciliation_difference: Decimal
    exportable: bool
    fiscal_year_source_sha256: str
    report_sha256: str
