import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app.modules.users.auth import TokenData, require_admin_or_staff
from .schemas import AdditionalDocumentInput, ExportRequest, Report, ReportRequest, ReviewInput, SourceKind, SourceView
from .service import GstReportingService
from .workbook import generate_workbook


router = APIRouter(prefix="/gst-reports", tags=["gst-reports"])


@router.get("/sources/{kind}/{identifier}", response_model=SourceView)
async def source(kind: SourceKind, identifier: int = Path(gt=0),
                 user: TokenData = Depends(require_admin_or_staff)):
    return await GstReportingService.source(kind, identifier)


@router.put("/sources/{kind}/{identifier}")
async def review(kind: SourceKind, data: ReviewInput, identifier: int = Path(gt=0),
                 user: TokenData = Depends(require_admin_or_staff)):
    return await GstReportingService.review(kind, identifier, data, user.user_id)


@router.post("/documents")
async def additional_document(data: AdditionalDocumentInput, user: TokenData = Depends(require_admin_or_staff)):
    return await GstReportingService.additional_document(data, user.user_id)


@router.get("/history/{source_key}")
async def history(source_key: str, user: TokenData = Depends(require_admin_or_staff)):
    return await GstReportingService.history(source_key)


@router.post("/reconcile", response_model=Report)
async def reconcile(data: ReportRequest, response: Response, user: TokenData = Depends(require_admin_or_staff)):
    response.headers["Cache-Control"] = "private, no-store"
    return await GstReportingService.report(data)


@router.post("/export")
async def export(data: ExportRequest, user: TokenData = Depends(require_admin_or_staff)):
    report = await GstReportingService.report(data.report)
    if report.report_sha256 != data.expected_report_sha256:
        raise HTTPException(status_code=409, detail="GST report changed since review; reconcile and approve the new report.")
    if not report.exportable:
        raise HTTPException(status_code=422, detail={
            "message": "GST export blocked by unresolved reconciliation issues.",
            "issues": [issue.model_dump(mode="json") for issue in report.issues],
        })
    content = await asyncio.to_thread(generate_workbook, report)
    filename = f"{report.seller_gstin}_GSTR1_{data.report.from_date}_{data.report.to_date}.xlsx"
    return Response(
        content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )
