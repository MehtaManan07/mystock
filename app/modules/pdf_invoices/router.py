from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import ValidationError as SchemaError

from app.core.exceptions import ValidationError
from app.modules.users.auth import TokenData, require_admin_or_staff, require_any_role
from .schemas import PdfInvoiceMetadata, PdfInvoicePage, PdfInvoiceResponse
from .service import MAX_PDF_BYTES, PdfInvoiceService


router = APIRouter(prefix="/pdf-invoices", tags=["pdf-invoices"])


@router.get("", response_model=PdfInvoicePage)
async def list_pdf_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    from_date: date | None = None,
    to_date: date | None = None,
    current_user: TokenData = Depends(require_any_role),
):
    return await PdfInvoiceService.list_invoices(page, page_size, search, from_date, to_date)


@router.post("", response_model=PdfInvoiceResponse, status_code=201)
async def upload_pdf_invoice(
    metadata: str = Form(..., max_length=200_000),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_admin_or_staff),
):
    try:
        parsed = PdfInvoiceMetadata.model_validate_json(metadata)
    except SchemaError as exc:
        message = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False)
        )
        raise ValidationError(message) from exc
    try:
        content = await file.read(MAX_PDF_BYTES + 1)
    finally:
        await file.close()
    filename = (file.filename or "invoice.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".pdf") or len(filename) > 255:
        raise ValidationError("Select a PDF filename no longer than 255 characters")
    return await PdfInvoiceService.register(parsed, content, filename, current_user.user_id)


@router.get("/{invoice_id}", response_model=PdfInvoiceResponse)
async def get_pdf_invoice(invoice_id: int, current_user: TokenData = Depends(require_any_role)):
    return await PdfInvoiceService.get_invoice(invoice_id)


@router.get("/{invoice_id}/file")
async def download_pdf_invoice(invoice_id: int, current_user: TokenData = Depends(require_any_role)):
    content, filename = await PdfInvoiceService.download(invoice_id)
    return Response(
        content, media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
