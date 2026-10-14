from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.contacts.models import Contact
from app.modules.pdf_invoices.models import PdfInvoice
from app.modules.products.models import Product
from app.modules.settings.models import CompanySettings
from app.modules.transactions.models import Transaction, TransactionItem
from .models import GstReview
from .schemas import GstDocument, GstLine, RateTax, SourceView


CENT = Decimal("0.01")


def money(value) -> Decimal:
    # Legacy SQLite REAL columns can contain binary tails; accounting precision is paise.
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def seller_gstin(db: Session, *, required: bool = True) -> str | None:
    sellers = db.scalars(select(CompanySettings.seller_gstin).where(
        CompanySettings.is_active.is_(True), CompanySettings.deleted_at.is_(None),
    )).all()
    if len(sellers) != 1:
        if not required:
            logging.getLogger(__name__).warning("GST snapshot has no unambiguous seller; filing will require review.")
            return None
        raise ValidationError("GST reporting requires exactly one active company settings record")
    return sellers[0]


def latest_reviews(db: Session, key: str | None = None) -> dict[str, GstReview]:
    # Keep old revisions visible through the history endpoint; never update them.
    query = select(GstReview.source_key, func.max(GstReview.revision).label("revision"))
    if key is not None:
        query = query.where(GstReview.source_key == key)
    latest = query.group_by(GstReview.source_key).subquery()
    reviews = db.scalars(select(GstReview).join(latest, (
        (GstReview.source_key == latest.c.source_key) & (GstReview.revision == latest.c.revision)
    )).order_by(GstReview.source_key)).all()
    return {review.source_key: review for review in reviews}


def rate_taxes(lines: list[GstLine], tax_type: str) -> list[RateTax]:
    if any(line.tax_rate is None or line.tax_amount is None for line in lines):
        return []
    buckets: dict[Decimal, Decimal] = defaultdict(Decimal)
    for line in lines:
        if line.tax_rate is not None and line.tax_amount is not None:
            buckets[line.tax_rate] += line.tax_amount
    result = []
    for rate, tax in sorted(buckets.items()):
        half = money(tax / 2)
        result.append(RateTax(
            rate=rate, igst=tax if tax_type == "igst" else 0,
            cgst=half if tax_type == "cgst_sgst" else 0,
            sgst=tax - half if tax_type == "cgst_sgst" else 0,
        ))
    return result


def raw_sources(db: Session, start, end, *, capture: bool = False, only_key: str | None = None):
    """Read accounting rows directly; historical HSN never comes from today's master."""
    tx_query = select(Transaction.__table__).where(Transaction.type == "sale")
    pdf_query = select(PdfInvoice.__table__)
    if only_key:
        kind, identifier = only_key.split(":")
        tx_query = tx_query.where(Transaction.id == int(identifier) if kind == "transaction" else False)
        pdf_query = pdf_query.where(PdfInvoice.id == int(identifier) if kind == "pdf_invoice" else False)
    else:
        tx_query = tx_query.where(Transaction.transaction_date.between(start, end))
        pdf_query = pdf_query.where(PdfInvoice.invoice_date.between(start, end))
    transactions = db.execute(tx_query.order_by(Transaction.id)).mappings().all()
    pdfs = db.execute(pdf_query.order_by(PdfInvoice.id)).mappings().all()
    ids = [row["id"] for row in transactions]
    items = db.execute(select(TransactionItem.__table__).where(
        TransactionItem.transaction_id.in_(ids),
    ).order_by(TransactionItem.id)).mappings().all() if ids else []
    by_transaction = defaultdict(list)
    for item in items:
        by_transaction[item["transaction_id"]].append(item)
    contacts = {row["id"]: row for row in db.execute(select(Contact.__table__).where(
        Contact.id.in_({row["contact_id"] for row in transactions}),
    )).mappings()} if transactions else {}
    products = {row["id"]: row for row in db.execute(select(Product.__table__).where(
        Product.id.in_({item["product_id"] for item in items}),
    )).mappings()} if items else {}
    seller = seller_gstin(db, required=not capture)
    fallback_hsn = None
    if capture:
        fallback_hsn = db.scalar(select(CompanySettings.hsn_code).where(
            CompanySettings.is_active.is_(True), CompanySettings.deleted_at.is_(None),
        ).limit(1)) if seller else None
    result = {}
    for row in transactions:
        contact = contacts[row["contact_id"]]
        lines = []
        item_rows = by_transaction[row["id"]]
        for item in item_rows:
            product = products[item["product_id"]]
            lines.append(GstLine(
                line_key=str(item["id"]), description=product["name"], quantity=item["quantity"],
                unit_price=money(item["unit_price"]),
                taxable_value=money(item["line_total"]),
                tax_rate=money(item["tax_rate"]) if item["tax_rate"] is not None else None,
                tax_amount=money(item["tax_amount"]) if item["tax_amount"] is not None else None,
                hsn=(product["hsn_code"] or fallback_hsn) if capture else None,
                treatment="taxable" if item["tax_rate"] is not None and item["tax_rate"] > 0 else "unknown",
            ))
        document = GstDocument(
            number=row["transaction_number"], date=row["transaction_date"],
            seller_gstin=seller, customer_name=contact["name"], customer_gstin=contact["gstin"],
            tax_type=row["tax_type"], subtotal=money(row["subtotal"]), tax_amount=money(row["tax_amount"]),
            total_amount=money(row["total_amount"]), discount_amount=money(row["discount_amount"]),
            round_off=money(row["total_amount"]) - money(row["subtotal"]) - money(row["tax_amount"]) + money(row["discount_amount"]),
            lines=lines, rate_taxes=rate_taxes(lines, row["tax_type"]),
        )
        if document.rate_taxes:
            for component in ("cgst", "sgst", "igst"):
                setattr(document, component, sum((getattr(bucket, component) for bucket in document.rate_taxes), Decimal(0)))
        # Payments and generated PDF URLs do not change the underlying sale.
        identity = {key: row[key] for key in (
            "id", "transaction_number", "transaction_date", "contact_id", "subtotal",
            "tax_amount", "total_amount", "discount_amount", "tax_type", "deleted_at",
        )}
        identity["items"] = [{key: item[key] for key in (
            "id", "product_id", "quantity", "unit_price", "line_total", "tax_rate", "tax_amount", "deleted_at",
        )} for item in item_rows]
        result[f"transaction:{row['id']}"] = (document, sha(identity), row["deleted_at"] is not None, True)
    for row in pdfs:
        stored_lines = row["line_items"] or []
        if isinstance(stored_lines, str):
            stored_lines = json.loads(stored_lines)
        lines = [GstLine(
            line_key=str(index), description=item["name"], quantity=item["quantity"],
            unit_price=item["unit_price"],
            taxable_value=money(Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))),
            tax_rate=item.get("tax_rate"),
            tax_amount=money(Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"])) * Decimal(str(item["tax_rate"])) / 100)
            if item.get("tax_rate") is not None else None,
            hsn=item.get("hsn_code"),
            treatment="taxable" if item.get("tax_rate") is not None and Decimal(str(item["tax_rate"])) > 0 else "unknown",
        ) for index, item in enumerate(stored_lines, 1)]
        tax_type = "igst" if row["igst"] else "cgst_sgst"
        document = GstDocument(
            number=row["invoice_number"], date=row["invoice_date"], seller_gstin=seller,
            customer_name=row["customer_name"], customer_gstin=row["customer_gstin"],
            tax_type=tax_type, subtotal=money(row["subtotal"]),
            tax_amount=money(row["cgst"]) + money(row["sgst"]) + money(row["igst"]),
            cgst=money(row["cgst"]), sgst=money(row["sgst"]), igst=money(row["igst"]),
            total_amount=money(row["total_amount"]), round_off=money(row["round_off"]),
            lines=lines, rate_taxes=rate_taxes(lines, tax_type),
        )
        if len(document.rate_taxes) == 1:
            document.rate_taxes[0] = RateTax(
                rate=document.rate_taxes[0].rate, cgst=money(row["cgst"]), sgst=money(row["sgst"]), igst=money(row["igst"]),
            )
        identity = {key: value for key, value in row.items() if key not in (
            "created_at", "updated_at", "upload_status", "storage_key", "original_filename",
        )}
        result[f"pdf_invoice:{row['id']}"] = (document, sha(identity), row["deleted_at"] is not None, row["upload_status"] == "ready")
    return result


def source_view(key, raw, review: GstReview | None) -> SourceView:
    document, fingerprint, deleted, ready = raw
    return SourceView(
        source_key=key, source_sha256=fingerprint, revision=review.revision if review else 0,
        verified=review.verified if review else False, source_deleted=deleted, upload_ready=ready,
        stale_review=bool(review and review.source_sha256 != fingerprint),
        disposition=review.disposition if review else ("cancelled" if deleted else "include"),
        evidence=review.evidence if review else None,
        document=GstDocument.model_validate(review.document) if review else document,
        source_document=document,
    )


def read_source(db: Session, key: str) -> SourceView:
    raw = raw_sources(db, None, None, only_key=key)
    if key not in raw:
        raise NotFoundError("GST invoice source", key)
    return source_view(key, raw[key], latest_reviews(db, key).get(key))


def capture_source(db: Session, kind: str, source_id: int) -> None:
    """Called inside the existing creation transaction; not a historical backfill."""
    key = f"{kind}:{source_id}"
    document, fingerprint, _, _ = raw_sources(db, None, None, capture=True, only_key=key)[key]
    db.add(GstReview(
        source_key=key, revision=1, document_date=document.date, source_sha256=fingerprint,
        document=document.model_dump(mode="json"), disposition="include", verified=False,
        evidence="Automatically captured at creation. Place of supply, UQC and filing classification require review.",
    ))
