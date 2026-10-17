from datetime import date
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from .models import GstReview
from .reporting import build_report
from .schemas import AdditionalDocumentInput, GstDocument, ReportRequest, ReviewInput, SourceView
from .sources import latest_reviews, raw_sources, read_source, seller_gstin, sha, source_view


logger = logging.getLogger(__name__)


def assert_source_preserved(original: GstDocument, reviewed: GstDocument) -> None:
    fields = ("number", "date", "kind", "subtotal", "tax_amount", "total_amount", "discount_amount", "round_off", "tax_type")
    for field in fields:
        if getattr(original, field) != getattr(reviewed, field):
            raise ValidationError(f"Reporting cannot change source {field}; correct the source through its approved workflow.")
    for field in ("cgst", "sgst", "igst"):
        value = getattr(original, field)
        if value is not None and getattr(reviewed, field) != value:
            raise ValidationError(f"Reporting cannot change source {field}; reconcile to the original tax split.")
    if not original.lines:
        return
    expected = {line.line_key: line for line in original.lines}
    actual = {line.line_key: line for line in reviewed.lines}
    if len(actual) != len(reviewed.lines) or set(expected) != set(actual):
        raise ValidationError("Reporting lines must match source line keys; do not re-enter or omit invoice lines.")
    for key, line in expected.items():
        for field in ("quantity", "unit_price", "taxable_value", "tax_rate", "tax_amount"):
            value = getattr(line, field)
            if value is not None and getattr(actual[key], field) != value:
                raise ValidationError(f"Line {key}: reporting cannot change the source {field}.")


def append_review(db, key, fingerprint, data, user_id):
    previous = db.scalars(select(GstReview).where(GstReview.source_key == key).order_by(
        GstReview.revision.desc(),
    ).limit(1)).first()
    revision = previous.revision if previous else 0
    payload = data.document.model_dump(mode="json")
    if previous and revision == data.expected_revision + 1 and (
        previous.document == payload and previous.disposition == data.disposition
        and previous.evidence == data.evidence and previous.source_sha256 == fingerprint
        and previous.reviewed_by_id == user_id
    ):
        return previous
    if revision != data.expected_revision:
        raise ConflictError("GST review changed concurrently; reload the source and review the latest revision.")
    row = GstReview(
        source_key=key, revision=revision + 1, document_date=data.document.date,
        source_sha256=fingerprint, document=payload, disposition=data.disposition,
        verified=True, evidence=data.evidence, reviewed_by_id=user_id,
    )
    db.add(row)
    db.flush()
    logger.info("GST reporting review appended: source=%s revision=%s reviewer=%s", key, row.revision, user_id)
    return row


def review_response(row):
    return {
        "id": row.id, "source_key": row.source_key, "revision": row.revision,
        "source_sha256": row.source_sha256, "document": row.document,
        "disposition": row.disposition, "verified": row.verified,
        "evidence": row.evidence, "reviewed_by_id": row.reviewed_by_id,
        "created_at": row.created_at,
    }


_REVISION_CONFLICT_MARKER = "uq_gst_review_revision"

_REVISION_CONFLICT_MESSAGE = (
    "A concurrent GST review won the revision; reload before retrying."
)


def _is_revision_conflict(exc: BaseException) -> bool:
    """True if `exc` is the (source_key, revision) unique violation."""
    return _REVISION_CONFLICT_MARKER in str(exc)


async def guarded_write(operation):
    try:
        return await run_db(operation)
    except IntegrityError as exc:
        if not _is_revision_conflict(exc):
            raise
        raise ConflictError(_REVISION_CONFLICT_MESSAGE) from exc


class GstReportingService:
    @staticmethod
    async def source(kind: str, identifier: int) -> SourceView:
        return await run_db(lambda db: read_source(db, f"{kind}:{identifier}"))

    @staticmethod
    async def review(kind: str, identifier: int, data: ReviewInput, user_id: int):
        def write(db):
            key = f"{kind}:{identifier}"
            original = raw_sources(db, None, None, only_key=key).get(key)
            if original is None:
                raise NotFoundError("GST source", key)
            document, fingerprint, deleted, _ = original
            if data.expected_source_sha256 != fingerprint:
                raise ConflictError("Invoice changed after it was loaded; reload before reviewing.")
            assert_source_preserved(document, data.document)
            if deleted and data.disposition == "include":
                raise ValidationError("A deleted source cannot be included; establish its cancellation/replacement first.")
            return review_response(append_review(db, key, fingerprint, data, user_id))
        return await guarded_write(write)

    @staticmethod
    async def additional_document(data: AdditionalDocumentInput, user_id: int):
        def write(db):
            key = f"additional:{data.key}"
            previous = db.scalars(select(GstReview).where(GstReview.source_key == key).order_by(
                GstReview.revision.desc(),
            ).limit(1)).first()
            if previous:
                original = GstDocument.model_validate(previous.document)
                if (original.number, original.date, original.kind) != (data.document.number, data.document.date, data.document.kind):
                    raise ValidationError("Do not change an additional document's identity/date; retain it and record the proper cancellation/replacement.")
            fingerprint = sha(data.document.model_dump(mode="json"))
            return review_response(append_review(db, key, fingerprint, data, user_id))
        return await guarded_write(write)

    @staticmethod
    async def history(source_key: str):
        def read(db):
            rows = db.scalars(select(GstReview).where(GstReview.source_key == source_key).order_by(GstReview.revision)).all()
            return [review_response(row) for row in rows]
        return await run_db(read)

    @staticmethod
    async def report(request: ReportRequest):
        def read(db):
            start_year = request.from_date.year if request.from_date.month >= 4 else request.from_date.year - 1
            fy_start, fy_end = date(start_year, 4, 1), date(start_year + 1, 3, 31)
            sources = raw_sources(db, fy_start, fy_end)
            reviews = latest_reviews(db)
            missing = []
            for key, review in reviews.items():
                if key.startswith("additional:") or key in sources or not fy_start <= review.document_date <= fy_end:
                    continue
                # A moved or physically removed source must not disappear from its reviewed period.
                current = raw_sources(db, None, None, only_key=key)
                if current:
                    sources.update(current)
                else:
                    missing.append(SourceView(
                        source_key=key, source_sha256=review.source_sha256, revision=review.revision,
                        verified=review.verified, source_deleted=True, upload_ready=False, stale_review=True,
                        disposition=review.disposition, evidence=review.evidence,
                        document=GstDocument.model_validate(review.document),
                    ))
            views = [source_view(key, source, reviews.get(key)) for key, source in sources.items()]
            views.extend(missing)
            for key, review in reviews.items():
                if key.startswith("additional:") and fy_start <= review.document_date <= fy_end:
                    views.append(SourceView(
                        source_key=key, source_sha256=review.source_sha256, revision=review.revision,
                        verified=review.verified, source_deleted=False, upload_ready=True, stale_review=False,
                        disposition=review.disposition, evidence=review.evidence,
                        document=GstDocument.model_validate(review.document),
                    ))
            views.sort(key=lambda view: (view.document.date, view.source_key))
            return build_report(request, seller_gstin(db), views)
        return await run_db(read)
