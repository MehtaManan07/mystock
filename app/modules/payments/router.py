"""
Payments Router - FastAPI routes for manual payments management.
Uses the unified Payment model from transactions module.
Protected with role-based access control.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import (
    TokenData,
    require_admin,
    require_admin_or_staff,
    require_admin_or_manager,
    require_any_role,
)
from .service import PaymentsService
from .models import SUGGESTED_PAYMENT_CATEGORIES, INCOME_CATEGORIES
from .schemas import (
    ManualPaymentResponse,
    ManualPaymentListItemResponse,
    CreateManualPaymentDto,
    UpdateManualPaymentDto,
    FilterManualPaymentsDto,
    PaymentSummaryResponse,
    SuggestedCategoriesResponse,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/suggested-categories", response_model=SuggestedCategoriesResponse)
async def get_suggested_categories(
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get suggested payment categories.

    Returns a list of commonly used payment categories that users can choose from.
    This includes both hardcoded suggestions AND user-created custom categories.
    Users are NOT restricted to these categories - they can create their own custom categories.

    Returns two lists: income and expense categories.
    """
    # Start with hardcoded suggestions
    income = set(c for c in SUGGESTED_PAYMENT_CATEGORIES if c in INCOME_CATEGORIES)
    expense = set(c for c in SUGGESTED_PAYMENT_CATEGORIES if c not in INCOME_CATEGORIES)
    
    # Fetch user-created categories from the database and merge
    user_categories = await PaymentsService.get_distinct_categories(db)
    income.update(user_categories.get('income', []))
    expense.update(user_categories.get('expense', []))
    
    return SuggestedCategoriesResponse(
        income_categories=sorted(income),
        expense_categories=sorted(expense)
    )


@router.post("", response_model=ManualPaymentResponse, status_code=201)
async def create_manual_payment(
    create_dto: CreateManualPaymentDto,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_staff)
):
    """
    Create a new payment entry. (Admin/Staff only)

    This endpoint supports TWO types of payments:

    **1. Manual Payments (transaction_id = null):**
    - For standalone expenses like rent, electricity, salaries, etc.
    - Requires: `category` and `description`
    - Example: Recording office rent payment

    **2. Transaction-Linked Payments (transaction_id = value):**
    - For payments against existing sales/purchase invoices
    - Automatically updates the transaction's paid_amount and payment_status
    - `category` is optional (defaults to 'transaction_payment')
    - `description` is optional
    - Example: Recording a payment against invoice #123

    **When to use transaction_id:**
    - Use this endpoint with `transaction_id` if you want more control
    - Alternative: Use POST /api/transactions/{id}/payments for simpler invoice payments
    """
    payment = await PaymentsService.create(db, create_dto)
    return payment


@router.get("", response_model=List[ManualPaymentListItemResponse])
async def get_all_manual_payments(
    filters: FilterManualPaymentsDto = Depends(),
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_any_role)
):
    """
    Get all payments with optional filters. (Requires authentication)

    By default, returns ALL payments (both manual and transaction-linked).
    Use `manual_only=true` to get only manual payments.

    Query parameters:
    - manual_only: If true, only show manual payments (not linked to transactions)
    - transaction_id: Filter by specific transaction
    - category: Filter by category (rent, electricity, etc.)
    - payment_method: Filter by payment method (cash, bank_transfer, upi, etc.)
    - contact_id: Filter by contact
    - from_date: Filter from this date (YYYY-MM-DD)
    - to_date: Filter to this date (YYYY-MM-DD)
    - min_amount: Minimum amount
    - max_amount: Maximum amount
    - search: Search in description

    Examples:
    - GET /payments - Get all payments
    - GET /payments?manual_only=true - Get only manual payments
    - GET /payments?transaction_id=123 - Get payments for transaction #123
    - GET /payments?category=rent - Get all rent payments
    - GET /payments?from_date=2024-01-01&to_date=2024-12-31 - Get payments for 2024
    """
    payments = await PaymentsService.find_all(db=db, filters=filters)
    return payments


@router.get("/summary", response_model=PaymentSummaryResponse)
async def get_manual_payments_summary(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_manager)
):
    """
    Get summary of manual payments with separate spends and earnings. (Admin/Manager only)

    Returns:
    - Total amount of all payments (spends + earnings)
    - Total spends (expenses like rent, electricity, salaries, etc.)
    - Total earnings (income like sales_income, service_income, etc.)
    - Count of transactions
    - Breakdown by category

    Query parameters:
    - from_date: Start date for filtering (YYYY-MM-DD)
    - to_date: End date for filtering (YYYY-MM-DD)

    Examples:
    - GET /payments/summary - Get summary for all time
    - GET /payments/summary?from_date=2024-01-01&to_date=2024-12-31 - Get 2024 summary
    """
    from datetime import date as date_type

    # Convert string dates to date objects for proper SQL type handling
    parsed_from_date = date_type.fromisoformat(from_date) if from_date else None
    parsed_to_date = date_type.fromisoformat(to_date) if to_date else None

    summary = await PaymentsService.get_summary(db, parsed_from_date, parsed_to_date)
    return summary


@router.get("/{payment_id}", response_model=ManualPaymentResponse)
async def get_manual_payment_by_id(
    payment_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_any_role)
):
    """Get payment by ID (supports both manual and transaction-linked payments) - requires authentication"""
    payment = await PaymentsService.find_one(db, payment_id)
    return payment


@router.patch("/{payment_id}", response_model=ManualPaymentResponse)
async def update_manual_payment(
    payment_id: int,
    update_dto: UpdateManualPaymentDto,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_staff)
):
    """
    Update payment information. (Admin/Staff only)

    Supports updating both manual and transaction-linked payments.
    If you update a transaction-linked payment's amount or transaction_id,
    the transaction's paid_amount and payment_status will be automatically updated.
    """
    payment = await PaymentsService.update(db, payment_id, update_dto)
    return payment


@router.delete("/{payment_id}")
@skip_interceptor
async def delete_manual_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin)
):
    """
    Soft delete payment. (Admin only)

    If the payment is linked to a transaction, automatically updates
    the transaction's paid_amount and payment_status.
    """
    await PaymentsService.remove(db, payment_id)
    return {"message": "Payment deleted successfully"}
