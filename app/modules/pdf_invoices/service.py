import asyncio
import hashlib
import json
import logging
from datetime import date

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from requests.exceptions import RequestException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import config
from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, ExternalServiceError, NotFoundError, ValidationError
from app.core.storage import ImmutableObjectConflictError, StorageService
from app.modules.transactions.models import Transaction
from .models import PdfInvoice
from .schemas import PdfInvoiceMetadata, PdfInvoicePage, PdfInvoiceResponse, financial_year


logger = logging.getLogger(__name__)
MAX_PDF_BYTES = 10 * 1024 * 1024


def validate_pdf(content: bytes) -> None:
    if not content or len(content) > MAX_PDF_BYTES:
        raise ValidationError("Select a PDF no larger than 10 MB")
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
        raise ValidationError("The uploaded file is not a complete PDF")


class PdfInvoiceService:
    @staticmethod
    def _reserve(
        db: Session, metadata: PdfInvoiceMetadata, content: bytes, filename: str, user_id: int
    ) -> PdfInvoice:
        pdf_hash = hashlib.sha256(content).hexdigest()
        canonical = json.dumps(metadata.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        metadata_hash = hashlib.sha256(canonical.encode()).hexdigest()
        year = financial_year(metadata.invoice_date)
        matches = db.scalars(select(PdfInvoice).where(or_(
            PdfInvoice.pdf_sha256 == pdf_hash,
            (PdfInvoice.invoice_number == metadata.invoice_number) & (PdfInvoice.financial_year == year),
        ))).all()
        if matches:
            if len(matches) == 1 and matches[0].pdf_sha256 == pdf_hash and matches[0].metadata_sha256 == metadata_hash:
                return matches[0]
            raise ConflictError("This PDF or invoice number is already registered with different details")

        existing = db.execute(select(Transaction.id).where(or_(
            func.upper(Transaction.transaction_number) == metadata.invoice_number,
            Transaction.invoice_checksum == hashlib.md5(content).hexdigest(),
        )).limit(1)).first()
        if existing:
            raise ConflictError("This invoice is already tracked in Transactions; do not register it twice")

        prefix = config.gcp_invoice_prefix.strip("/")
        storage_key = f"{prefix + '/' if prefix else ''}standalone/{year}/{pdf_hash}.pdf"
        row = PdfInvoice(
            **metadata.model_dump(exclude={"line_items"}),
            line_items=[item.model_dump(mode="json") for item in metadata.line_items] if metadata.line_items else None,
            financial_year=year,
            original_filename=filename,
            pdf_sha256=pdf_hash,
            metadata_sha256=metadata_hash,
            storage_key=storage_key,
            upload_status="pending",
            created_by_id=user_id,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    async def register(metadata: PdfInvoiceMetadata, content: bytes, filename: str, user_id: int) -> PdfInvoiceResponse:
        validate_pdf(content)
        if not config.gcp_bucket_name:
            raise ValidationError("Cloud invoice storage is not configured")

        def reserve(db):
            return PdfInvoiceService._reserve(db, metadata, content, filename, user_id)

        try:
            row = await run_db(reserve)
        except (IntegrityError, ValueError) as exc:
            if "unique constraint failed: pdf_invoices." not in str(exc).lower():
                raise
            # A concurrent identical upload may have won the unique-key race.
            row = await run_db(reserve)
        if row.upload_status == "ready":
            return PdfInvoiceResponse.model_validate(row)

        # Persist the pending record first. Retries reuse it and the immutable object,
        # including when the previous upload succeeded but the final DB commit failed.
        logger.info("Uploading PDF invoice %s (register id %s)", row.invoice_number, row.id)
        try:
            await asyncio.to_thread(
                StorageService.upload_file, content, row.storage_key, "application/pdf",
                {"pdf_invoice_id": str(row.id), "invoice_number": row.invoice_number},
                immutable=True,
            )
        except ImmutableObjectConflictError as exc:
            logger.exception("Immutable object mismatch for PDF invoice id %s", row.id)
            raise ConflictError("The archive object differs from this PDF. Contact an administrator; no file was overwritten") from exc
        except (GoogleAPIError, GoogleAuthError, RequestException, OSError) as exc:
            logger.exception("Cloud upload failed for PDF invoice id %s", row.id)
            raise ExternalServiceError("Cloud storage", "Upload incomplete. Retry with the same PDF and details") from exc

        def finish(db):
            saved = db.get(PdfInvoice, row.id)
            if saved is None:
                raise NotFoundError("PDF invoice", row.id)
            saved.upload_status = "ready"
            db.flush()
            return PdfInvoiceResponse.model_validate(saved)

        return await run_db(finish)

    @staticmethod
    async def list_invoices(page: int, page_size: int, search: str | None, from_date: date | None, to_date: date | None) -> PdfInvoicePage:
        if from_date and to_date and from_date > to_date:
            raise ValidationError("From date must not be after to date")

        def read(db):
            query = select(PdfInvoice).where(PdfInvoice.deleted_at.is_(None))
            if search and search.strip():
                pattern = f"%{search.strip()}%"
                query = query.where(or_(
                    PdfInvoice.invoice_number.ilike(pattern),
                    PdfInvoice.customer_name.ilike(pattern),
                    PdfInvoice.customer_gstin.ilike(pattern),
                ))
            if from_date:
                query = query.where(PdfInvoice.invoice_date >= from_date)
            if to_date:
                query = query.where(PdfInvoice.invoice_date <= to_date)
            total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = db.scalars(query.order_by(
                PdfInvoice.invoice_date.desc(), PdfInvoice.id.desc()
            ).offset((page - 1) * page_size).limit(page_size)).all()
            return PdfInvoicePage(
                items=[PdfInvoiceResponse.model_validate(row) for row in rows],
                total=total, page=page, page_size=page_size, has_more=page * page_size < total,
            )

        return await run_db(read)

    @staticmethod
    async def get_invoice(invoice_id: int) -> PdfInvoice:
        def read(db):
            row = db.get(PdfInvoice, invoice_id)
            if row is None or row.deleted_at is not None:
                raise NotFoundError("PDF invoice", invoice_id)
            return row
        return await run_db(read)

    @staticmethod
    async def download(invoice_id: int) -> tuple[bytes, str]:
        row = await PdfInvoiceService.get_invoice(invoice_id)
        if row.upload_status != "ready":
            raise ConflictError("Upload incomplete. Re-upload the same PDF and metadata to retry")
        try:
            content = await asyncio.to_thread(StorageService.download_file, row.storage_key)
        except (GoogleAPIError, GoogleAuthError, RequestException, OSError) as exc:
            logger.exception("Cloud download failed for PDF invoice id %s", row.id)
            raise ExternalServiceError("Cloud storage", "PDF download failed. Please retry") from exc
        if hashlib.sha256(content).hexdigest() != row.pdf_sha256:
            logger.error("Stored PDF checksum mismatch for register id %s", row.id)
            raise ConflictError("Stored PDF failed its integrity check; download stopped")
        return content, row.invoice_number.replace("/", "-") + ".pdf"
