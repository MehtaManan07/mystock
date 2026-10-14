from collections import defaultdict
from decimal import Decimal
import re

from app.core.exceptions import ValidationError
from .schemas import GstDocument, Issue, Report, ReportRequest, SalesGroup, SourceView, Totals
from .sources import money, sha


STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
    "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman and Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory",
}
UQCS = {
    "BAG", "BAL", "BDL", "BKL", "BOU", "BOX", "BTL", "BUN", "CAN", "CBM", "CCM",
    "CMS", "CTN", "DOZ", "DRM", "GGK", "GMS", "GRS", "GYD", "KGS", "KLR", "KME",
    "LTR", "MTR", "MTS", "NOS", "PAC", "PCS", "PRS", "QTL", "ROL", "SET", "SQF",
    "SQM", "SQY", "TBS", "TGM", "THD", "TON", "TUB", "UGS", "UNT", "YDS", "OTH",
}
RATES = {Decimal(value) for value in ("0", "0.1", "0.25", "1", "1.5", "3", "5", "6", "7.5", "12", "18", "28")}
UQC_LABELS = {
    "NOS": "NOS-NUMBERS", "PCS": "PCS-PIECES", "SET": "SET-SETS", "PAC": "PAC-PACKS",
    "BOX": "BOX-BOX", "CTN": "CTN-CARTONS", "KGS": "KGS-KILOGRAMS",
    "GMS": "GMS-GRAMMES", "MTR": "MTR-METERS", "SQM": "SQM-SQUARE METERS",
    "LTR": "LTR-LITRES", "OTH": "OTH-OTHERS", "NA": "NA",
}
ATTESTATIONS = {
    "sources_complete": "Confirm all invoices and supplier-issued adjustment documents are present.",
    "no_iff_or_previously_filed_records": "Previously furnished IFF/return records require a separate reconciliation; do not re-upload them.",
    "no_unsupported_supplies_or_amendments": "Confirm no exports, SEZ/deemed exports, ECO tables, advances, cess, amendments or other unsupported sections are required.",
    "cross_period_and_cancellations_reviewed": "Confirm cross-period replacements, supply timing, credit notes and cancelled documents have been reviewed.",
    "gstin_hsn_and_uqc_verified": "Confirm recipient registration status and HSN/UQC validity against official records.",
    "document_series_complete": "Confirm every invoice/bill-of-supply series, including cancelled serials, is complete.",
}


def valid_gstin(value: str | None) -> bool:
    if not value or not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", value):
        return False
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for index, char in enumerate(value[:14]):
        product = alphabet.index(char) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return value[:2] in STATES and value[-1] == alphabet[(36 - total % 36) % 36]


def document_issues(doc: GstDocument, key: str, minimum_hsn_digits: int) -> list[Issue]:
    issues = []

    def problem(code, message):
        issues.append(Issue(code=code, message=message, source_key=key))

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/-]{0,15}", doc.number):
        problem("invoice_number", "GST document number must be 1-16 alphanumeric, slash or dash characters.")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", doc.customer_name):
        problem("customer_name", "Recipient name contains control characters unsupported by Excel.")
    if not valid_gstin(doc.seller_gstin) or (doc.customer_gstin is not None and not valid_gstin(doc.customer_gstin)):
        problem("gstin", "Seller or recipient GSTIN is malformed or has an invalid checksum.")
    if doc.place_of_supply not in STATES:
        problem("place_of_supply", "Explicit, verified domestic place of supply is required; it is not inferred from GSTIN/address.")
    if doc.invoice_type != "regular" or doc.reverse_charge is None:
        problem("invoice_classification", "Confirm regular domestic supply and reverse-charge status; other invoice types are not supported.")
    if doc.reverse_charge and not doc.customer_gstin:
        problem("unregistered_reverse_charge", "Unregistered reverse-charge supplies are outside this workbook scope.")
    if doc.cess_amount or doc.discount_amount:
        problem("unsupported_amount", "Cess and invoice-level discounts require an explicitly supported taxable allocation.")
    if doc.kind != "invoice":
        if not doc.original_invoice_number or not doc.original_invoice_date:
            problem("note_reference", "Supplier credit/debit notes require an original invoice number and date.")
        elif doc.original_invoice_date > doc.date:
            problem("note_date", "The original invoice cannot be dated after its credit/debit note.")
        if not doc.customer_gstin and doc.original_invoice_value is None:
            problem("unregistered_note_value", "Unregistered credit/debit notes need the original invoice value to determine B2CL versus B2CS.")
    if doc.original_invoice_number and doc.kind == "invoice":
        problem("unexpected_reference", "Invoice reference fields are reserved for credit/debit notes.")
    if not doc.series:
        problem("series", "Assign the actual document series for the documents-issued summary.")
    if not doc.lines:
        problem("missing_lines", "Historical item/HSN/quantity data is missing. Supply verified evidence, not today's product defaults.")
    if len({line.line_key for line in doc.lines}) != len(doc.lines):
        problem("duplicate_line_key", "Each reporting line must have a unique source line key.")
    if sum((line.taxable_value for line in doc.lines), Decimal(0)) != doc.subtotal:
        problem("taxable_reconciliation", "Sum of line values does not match the source subtotal.")
    line_tax = sum((line.tax_amount or Decimal(0) for line in doc.lines), Decimal(0))
    if line_tax != doc.tax_amount:
        problem("tax_reconciliation", "Sum of line tax amounts does not match the source tax.")
    for component in ("cgst", "sgst", "igst"):
        declared = getattr(doc, component)
        actual = sum((getattr(bucket, component) for bucket in doc.rate_taxes), Decimal(0))
        if declared is None or declared != actual:
            problem("component_reconciliation", f"Rate buckets must match the original document's explicit {component} total.")
    if doc.subtotal + doc.tax_amount - doc.discount_amount + doc.round_off != doc.total_amount or abs(doc.round_off) >= 1:
        problem("total_reconciliation", "Subtotal + tax - discount + rounding must match the original, with rounding below one rupee.")
    buckets = defaultdict(Decimal)
    for line in doc.lines:
        if line.treatment == "unknown":
            problem("supply_classification", f"Line {line.line_key}: zero/unknown GST does not establish exemption or non-GST status.")
        if line.treatment != "non_gst" and (
            not line.hsn or not re.fullmatch(r"(?:[0-9]{4}|[0-9]{6}|[0-9]{8})", line.hsn)
            or len(line.hsn) < minimum_hsn_digits
        ):
            problem("hsn", f"Line {line.line_key}: a verified {minimum_hsn_digits}+ digit HSN/SAC is required.")
        if line.uqc not in UQCS and not (line.uqc == "NA" and line.hsn and line.hsn.startswith("99")):
            problem("uqc", f"Line {line.line_key}: supply a verified UQC code (NOS, SET, PCS, etc.).")
        elif line.uqc not in UQC_LABELS:
            problem("unsupported_uqc", f"Line {line.line_key}: UQC {line.uqc} is not supported by this workbook version.")
        if line.quantity == 0 and not (line.hsn and line.hsn.startswith("99")):
            problem("quantity", f"Line {line.line_key}: goods require a positive quantity.")
        if line.unit_price is not None and money(line.quantity * line.unit_price) != line.taxable_value:
            problem("line_value_arithmetic", f"Line {line.line_key}: quantity times unit price differs from line value.")
        if line.tax_rate is None or line.tax_amount is None:
            problem("missing_tax_snapshot", f"Line {line.line_key}: historical GST rate and amount must be established.")
            continue
        if line.tax_rate not in RATES:
            problem("unsupported_rate", f"Line {line.line_key}: GST rate is not supported by this workbook version.")
        if line.treatment in ("nil_rated", "exempt", "non_gst"):
            if line.tax_amount or line.tax_rate:
                problem("exemption_tax", f"Line {line.line_key}: exempt/non-GST/nil supplies must have zero tax and rate.")
        elif line.treatment == "taxable" and line.tax_rate == 0:
            problem("zero_tax_classification", f"Line {line.line_key}: classify the zero-rated line explicitly.")
        if money(line.taxable_value * line.tax_rate / 100) != line.tax_amount:
            problem("line_tax_arithmetic", f"Line {line.line_key}: taxable value times GST rate differs from tax charged.")
        buckets[line.tax_rate] += line.tax_amount
    rates = [bucket.rate for bucket in doc.rate_taxes]
    if len(set(rates)) != len(rates) or set(rates) != set(buckets):
        problem("rate_summary", "Rate-wise CGST/SGST/IGST breakdown must cover each line rate exactly once.")
    for bucket in doc.rate_taxes:
        if bucket.cgst + bucket.sgst + bucket.igst != buckets[bucket.rate]:
            problem("rate_tax_reconciliation", f"Rate {bucket.rate}: tax components do not match line taxes.")
        if doc.tax_type == "igst" and (bucket.cgst or bucket.sgst):
            problem("tax_components", "An IGST document cannot contain CGST/SGST.")
        if doc.tax_type == "cgst_sgst" and (bucket.igst or abs(bucket.cgst - bucket.sgst) > Decimal(".01")):
            problem("tax_components", "Intra-state tax requires equal CGST/SGST, allowing only a one-paise split.")
    if doc.seller_gstin and doc.place_of_supply in STATES:
        interstate = doc.seller_gstin[:2] != doc.place_of_supply
        if doc.tax_amount and interstate != (doc.tax_type == "igst"):
            problem("tax_jurisdiction", "Tax type conflicts with seller state and confirmed place of supply.")
    return issues


def series_rows(views: list[SourceView]) -> tuple[list[list], list[Issue]]:
    groups = defaultdict(list)
    issues = []
    for view in views:
        if view.disposition in ("not_issued", "duplicate"):
            continue
        doc = view.document
        if not doc.series:
            continue
        match = re.fullmatch(r"(.*?)(\d+)(\D.*)?", doc.number)
        if not match:
            issues.append(Issue(code="series_number", message="Cannot establish numeric document sequence.", source_key=view.source_key))
            continue
        groups[(doc.kind, doc.series)].append((int(match[2]), match[1], match[3] or "", view))
    rows = []
    labels = {"invoice": "Invoices for outward supply", "credit_note": "Credit Note", "debit_note": "Debit Note"}
    for (kind, series), records in sorted(groups.items()):
        records.sort(key=lambda item: (item[0], item[3].source_key))
        serials = [item[0] for item in records]
        if len({(item[1], item[2]) for item in records}) != 1 or len(set(serials)) != len(serials):
            issues.append(Issue(code="series_collision", message=f"{series}: conflicting number formats or repeated serials."))
        if serials[-1] - serials[0] + 1 != len(set(serials)):
            issues.append(Issue(code="series_gap", message=f"{series}: serial gaps require original/cancelled document evidence, not invented counts."))
        rows.append([
            labels[kind], records[0][3].document.number, records[-1][3].document.number,
            len(records), sum(item[3].disposition == "cancelled" for item in records),
        ])
    return rows, issues


def build_report(request: ReportRequest, seller: str | None, all_views: list[SourceView]) -> Report:
    views = [view for view in all_views if (
        request.from_date <= view.document.date <= request.to_date
        or (view.source_document and request.from_date <= view.source_document.date <= request.to_date)
    )]
    issues = []
    if not valid_gstin(seller):
        issues.append(Issue(code="seller_gstin", message="Active company GSTIN is invalid."))
    for field, message in ATTESTATIONS.items():
        if not getattr(request, field):
            issues.append(Issue(code=field, message=message))
    identities = defaultdict(list)
    for view in all_views:
        doc = view.document
        if view.disposition not in ("duplicate", "not_issued"):
            identities[(doc.kind, doc.number.upper())].append(view)
    for identity, collisions in identities.items():
        if len(collisions) > 1 and any(view in views for view in collisions):
            issues.append(Issue(code="duplicate_identity", message=f"Repeated fiscal-year document identity {identity}: " + ", ".join(v.source_key for v in collisions)))
    totals = Totals()
    groups = {}
    excluded, included_total, excluded_total, source_total = [], Decimal(0), Decimal(0), Decimal(0)
    for view in views:
        doc = view.document
        sign = -1 if doc.kind == "credit_note" else 1
        source_total += sign * (view.source_document or doc).total_amount
        if not view.verified:
            issues.append(Issue(code="unreviewed", message="Source requires a documented GST review.", source_key=view.source_key))
        if view.stale_review:
            issues.append(Issue(code="stale_review", message="Source changed after the reporting review; review again.", source_key=view.source_key))
        if doc.seller_gstin != seller:
            issues.append(Issue(code="seller_mismatch", message="Document seller differs from the reporting GSTIN.", source_key=view.source_key))
        if view.disposition != "include":
            excluded.append(view.source_key)
            excluded_total += sign * doc.total_amount
            if view.disposition == "cancelled":
                if not doc.series or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/-]{0,15}", doc.number):
                    issues.append(Issue(code="cancelled_serial", message="Cancelled documents need a valid serial and series.", source_key=view.source_key))
            continue
        included_total += sign * doc.total_amount
        if view.source_deleted or not view.upload_ready:
            issues.append(Issue(code="source_not_active", message="Deleted or incomplete-upload source cannot be included as a sale.", source_key=view.source_key))
        issues.extend(document_issues(doc, view.source_key, 6 if request.preceding_year_turnover_above_5cr else 4))
        if doc.kind != "invoice" and doc.original_invoice_number:
            originals = [v.document for v in all_views if v.document.kind == "invoice"
                         and v.document.number.upper() == doc.original_invoice_number.upper()
                         and v.disposition == "include"]
            if originals and not any(
                original.date == doc.original_invoice_date and original.customer_gstin == doc.customer_gstin
                and (doc.customer_gstin is not None or original.customer_name.casefold() == doc.customer_name.casefold())
                and original.place_of_supply == doc.place_of_supply for original in originals
            ):
                issues.append(Issue(code="note_original_mismatch", message="Credit/debit note reference differs from its source invoice.", source_key=view.source_key))
            if doc.original_invoice_value is not None and originals and not any(
                original.total_amount == doc.original_invoice_value for original in originals
            ):
                issues.append(Issue(code="note_original_value", message="Original invoice value on the note differs from the source.", source_key=view.source_key))
            if len(originals) == 1:
                related = [v.document for v in all_views if v.disposition == "include"
                           and v.document.kind != "invoice" and v.document.original_invoice_number
                           and v.document.original_invoice_number.upper() == doc.original_invoice_number.upper()
                           and v.document.original_invoice_date == doc.original_invoice_date]
                for field in ("subtotal", "tax_amount", "total_amount"):
                    credited = sum((getattr(note, field) for note in related if note.kind == "credit_note"), Decimal(0))
                    available = getattr(originals[0], field) + sum((
                        getattr(note, field) for note in related if note.kind == "debit_note"
                    ), Decimal(0))
                    if credited > available:
                        issues.append(Issue(
                            code="excess_credit", message=f"Fiscal-year credit notes exceed the original invoice plus debit notes ({field}).",
                            source_key=view.source_key,
                        ))
        totals.total += sign * doc.total_amount
        totals.round_off += sign * doc.round_off
        for bucket in doc.rate_taxes:
            for tax in ("cgst", "sgst", "igst"):
                setattr(totals, tax, getattr(totals, tax) + sign * getattr(bucket, tax))
        for line in doc.lines:
            field = {"taxable": "taxable", "nil_rated": "nil_rated", "exempt": "exempt", "non_gst": "non_gst"}.get(line.treatment)
            if field:
                setattr(totals, field, getattr(totals, field) + sign * line.taxable_value)
            key = (doc.customer_gstin, doc.invoice_type, doc.place_of_supply, doc.kind, line.treatment, line.tax_rate)
            if key not in groups:
                groups[key] = SalesGroup(gstin=key[0], invoice_type=key[1], place_of_supply=key[2],
                                        document_kind=key[3], treatment=key[4], rate=key[5])
            group = groups[key]
            if field:
                setattr(group, field, getattr(group, field) + sign * line.taxable_value)
            if view.source_key not in group.source_keys:
                group.source_keys.append(view.source_key)
        for bucket in doc.rate_taxes:
            key = (doc.customer_gstin, doc.invoice_type, doc.place_of_supply, doc.kind, "taxable", bucket.rate)
            if key in groups:
                for tax in ("cgst", "sgst", "igst"):
                    setattr(groups[key], tax, getattr(groups[key], tax) + sign * getattr(bucket, tax))
    _, series_issues = series_rows(views)
    issues.extend(series_issues)
    summed = totals.taxable + totals.nil_rated + totals.exempt + totals.non_gst + totals.cgst + totals.sgst + totals.igst + totals.round_off
    if summed != totals.total:
        issues.append(Issue(code="report_totals", message="Classified turnover, tax and rounding do not reconcile to included invoice totals."))
    source_difference = source_total - included_total - excluded_total
    if source_difference:
        issues.append(Issue(code="source_totals", message="Current SQL amounts differ from the reviewed included/excluded document totals."))
    report = Report(
        request=request, seller_gstin=seller, documents=views, issues=issues,
        groups=[groups[key] for key in sorted(groups, key=lambda key: tuple(str(part) for part in key))],
        totals=totals, excluded_source_keys=excluded, source_invoice_total=source_total,
        included_document_total=included_total, excluded_document_total=excluded_total,
        source_reconciliation_difference=source_difference,
        fiscal_year_source_sha256=sha([view.model_dump(mode="json") for view in all_views]),
        exportable=not any(issue.severity == "blocker" for issue in issues), report_sha256="",
    )
    if report.exportable:
        # Reuse the actual section builder so reconciliation and export enforce the same restrictions.
        from .workbook import export_rows
        try:
            export_rows(report)
        except ValidationError as exc:
            report.issues.append(Issue(code="export_layout", message=str(exc.detail)))
            report.exportable = False
    report.report_sha256 = sha(report.model_dump(mode="json", exclude={"report_sha256"}))
    return report
