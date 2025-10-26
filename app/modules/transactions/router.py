"""
Transactions Router - FastAPI routes for sales and purchase transactions.
Handles transaction creation, payment recording, and financial reporting.
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from .service import TransactionsService
from .invoice_service import InvoiceService
from .schemas import (
    TransactionResponse,
    TransactionListItemResponse,
    CreateSaleDto,
    CreatePurchaseDto,
    CreatePaymentDto,
    PaymentResponse,
    TransactionFilterDto,
    InvoiceMetadataResponse,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/sales", response_model=TransactionResponse, status_code=201)
async def create_sale(
    sale_data: CreateSaleDto,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Create a new sale transaction.

    Automatically:
    - Generates transaction number (SALE-0001)
    - Deducts inventory from containers
    - Creates inventory logs
    - Updates customer balance
    - Creates payment record if paid_amount > 0

    Returns the complete transaction with all relationships.
    """
    transaction = await TransactionsService.create_sale(db, sale_data)
    return transaction


@router.post("/purchases", response_model=TransactionResponse, status_code=201)
async def create_purchase(
    purchase_data: CreatePurchaseDto,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Create a new purchase transaction.

    Automatically:
    - Generates transaction number (PUR-0001)
    - Adds inventory to containers
    - Creates inventory logs
    - Updates supplier balance
    - Creates payment record if paid_amount > 0

    Returns the complete transaction with all relationships.
    """
    transaction = await TransactionsService.create_purchase(db, purchase_data)
    return transaction


@router.get("", response_model=List[TransactionResponse])
async def list_transactions(
    type: str | None = Query(None, description="Filter by type: sale or purchase"),
    payment_status: str | None = Query(
        None, description="Filter by status: paid, partial, unpaid"
    ),
    contact_id: int | None = Query(None, description="Filter by contact ID"),
    from_date: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    search: str | None = Query(
        None, description="Search in transaction number or notes"
    ),
    db: AsyncSession = Depends(get_db_util),
):
    """
    List all transactions with optional filters.

    Query parameters:
    - type: Filter by transaction type (sale, purchase)
    - payment_status: Filter by payment status (paid, partial, unpaid)
    - contact_id: Filter by specific contact
    - from_date: Start date (YYYY-MM-DD)
    - to_date: End date (YYYY-MM-DD)
    - search: Search in transaction number or notes

    Examples:
    - GET /transactions - Get all transactions
    - GET /transactions?type=sale - Get all sales
    - GET /transactions?payment_status=unpaid - Get unpaid transactions
    - GET /transactions?contact_id=5 - Get transactions for specific contact
    - GET /transactions?from_date=2025-01-01&to_date=2025-01-31 - Get January transactions
    - GET /transactions?search=SALE-0001 - Search by transaction number

    Returns transactions ordered by date (newest first).
    """
    from datetime import date as date_type
    from .models import TransactionType, PaymentStatus

    # Build filters object
    filter_type = TransactionType(type) if type else None
    filter_payment_status = PaymentStatus(payment_status) if payment_status else None
    filter_from_date = date_type.fromisoformat(from_date) if from_date else None
    filter_to_date = date_type.fromisoformat(to_date) if to_date else None

    filters = TransactionFilterDto(
        type=filter_type,
        payment_status=filter_payment_status,
        contact_id=contact_id,
        from_date=filter_from_date,
        to_date=filter_to_date,
        search=search,
    )

    transactions = await TransactionsService.list_transactions(db, filters)
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get a single transaction by ID.

    Returns the complete transaction with:
    - Contact details
    - All line items with product and container info
    - All payment records
    """
    transaction = await TransactionsService.get_transaction(db, transaction_id)
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Delete a transaction (soft delete).

    Automatically reverses:
    - Inventory changes (restores quantities)
    - Contact balance changes
    - Soft deletes transaction, items, and payments

    Note: This is a destructive operation. Use with caution.
    """
    await TransactionsService.delete_transaction(db, transaction_id)
    return None


@router.post(
    "/{transaction_id}/payments", response_model=TransactionResponse, status_code=201
)
async def record_payment(
    transaction_id: int,
    payment_data: CreatePaymentDto,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Record a payment against an existing transaction.

    Automatically:
    - Creates payment record
    - Updates transaction paid_amount
    - Updates payment_status (unpaid → partial → paid)
    - Updates contact balance

    Validations:
    - Payment amount must be positive
    - Payment amount cannot exceed remaining balance
    - Transaction must not be already fully paid

    Returns the updated transaction with all relationships.
    """
    transaction = await TransactionsService.record_payment(
        db, transaction_id, payment_data
    )
    return transaction


@router.get("/{transaction_id}/payments", response_model=List[PaymentResponse])
async def get_transaction_payments(
    transaction_id: int,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get all payments for a specific transaction.

    Returns list of payment records ordered by payment date.
    """
    transaction = await TransactionsService.get_transaction(db, transaction_id)
    return transaction.payments


# Invoice Endpoints


@router.get(
    "/{transaction_id}/invoice/metadata", response_model=InvoiceMetadataResponse
)
async def get_invoice_metadata(
    transaction_id: int,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get invoice metadata (URL, checksum, status) without full transaction data.

    Ultra-optimized endpoint:
    - Returns only invoice-related fields
    - 1 DB query (~5ms)
    - No S3 API calls
    - Minimal bandwidth

    Use this endpoint to check if invoice exists and get its URL.
    """
    metadata = await InvoiceService.get_invoice_metadata(db, transaction_id)
    return metadata


@router.post("/{transaction_id}/invoice/generate", status_code=201)
async def generate_invoice(
    transaction_id: int,
    force_regenerate: bool = Query(
        False, description="Force regenerate if already exists"
    ),
    db: AsyncSession = Depends(get_db_util),
):
    """
    Manually generate/regenerate invoice PDF for a transaction.

    By default, invoices are auto-generated on transaction creation.
    Use this endpoint to:
    - Regenerate a corrupted invoice (force_regenerate=true)
    - Generate invoice for old transactions created before this feature

    Idempotent: Returns existing invoice URL if already generated (unless forced).

    Performance:
    - PDF generation: 50-100ms
    - S3 upload: 1 PUT request (~50ms)
    - Total: ~150-200ms
    """
    invoice_url, checksum = await InvoiceService.generate_and_upload_invoice(
        db, transaction_id, force_regenerate
    )

    return {
        "message": "Invoice generated successfully",
        "invoice_url": invoice_url,
        "checksum": checksum,
    }


@router.get("/{transaction_id}/invoice/download")
async def download_invoice(
    transaction_id: int,
    expiration: int = Query(
        3600, ge=300, le=86400, description="URL validity in seconds (5min - 24h)"
    ),
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get presigned URL for direct invoice download from S3.

    This is the MOST EFFICIENT way to serve invoices:
    - 0 bandwidth through our server
    - Client downloads directly from S3
    - Temporary access (security)
    - 0 S3 API calls (just URL generation)

    The returned URL is valid for the specified expiration time (default 1 hour).

    Performance:
    - 1 DB query (~5ms)
    - URL generation (~1ms)
    - Total: ~10ms

    Optimization:
    - No GET request to S3
    - No data transfer through server
    - Client fetches directly from S3
    """
    presigned_url = await InvoiceService.generate_presigned_url(
        db, transaction_id, expiration
    )

    return {
        "download_url": presigned_url,
        "expires_in_seconds": expiration,
        "note": "Download URL is temporary and expires after the specified time",
    }
