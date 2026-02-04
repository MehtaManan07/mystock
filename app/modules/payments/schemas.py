"""
Manual Payments DTOs (Data Transfer Objects)
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime, date
from decimal import Decimal
from .models import PaymentMethod, SUGGESTED_PAYMENT_CATEGORIES


# Request DTOs


class CreateManualPaymentDto(BaseModel):
    """DTO for creating a payment entry (can be manual or linked to a transaction)"""

    payment_date: date = Field(..., description="Date of payment")
    type: Optional[Literal['income', 'expense']] = Field(
        None, description="Explicit cashflow type: income or expense"
    )
    category: Optional[str] = Field(
        None, max_length=100, description="Category of payment (free text, optional for transaction-linked payments)"
    )
    amount: Decimal = Field(..., gt=0, description="Payment amount (must be positive)")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    transaction_id: Optional[int] = Field(
        None, gt=0, description="Optional transaction ID to link this payment to an invoice"
    )
    contact_id: Optional[int] = Field(
        None, gt=0, description="Optional contact ID (supplier, customer, etc.)"
    )
    description: Optional[str] = Field(
        None, min_length=1, max_length=500, description="Payment description"
    )
    reference_number: Optional[str] = Field(
        None, max_length=100, description="Payment reference number"
    )

    class Config:
        from_attributes = True


class UpdateManualPaymentDto(BaseModel):
    """DTO for updating a payment entry"""

    payment_date: Optional[date] = Field(None, description="Date of payment")
    type: Optional[Literal['income', 'expense']] = Field(
        None, description="Explicit cashflow type: income or expense"
    )
    category: Optional[str] = Field(None, max_length=100, description="Category of payment (free text)")
    amount: Optional[Decimal] = Field(
        None, gt=0, description="Payment amount (must be positive)"
    )
    payment_method: Optional[PaymentMethod] = Field(None, description="Payment method")
    transaction_id: Optional[int] = Field(
        None, gt=0, description="Optional transaction ID to link/unlink this payment"
    )
    contact_id: Optional[int] = Field(
        None, gt=0, description="Optional contact ID (supplier, customer, etc.)"
    )
    description: Optional[str] = Field(
        None, min_length=1, max_length=500, description="Payment description"
    )
    reference_number: Optional[str] = Field(
        None, max_length=100, description="Payment reference number"
    )

    class Config:
        from_attributes = True


class FilterManualPaymentsDto(BaseModel):
    """DTO for filtering payments"""

    type: Optional[Literal['income', 'expense']] = Field(
        None, description="Filter by cashflow type: income or expense"
    )
    category: Optional[str] = Field(
        None, max_length=100, description="Filter by category (free text)"
    )
    payment_method: Optional[PaymentMethod] = Field(
        None, description="Filter by payment method"
    )
    contact_id: Optional[int] = Field(None, gt=0, description="Filter by contact")
    transaction_id: Optional[int] = Field(None, gt=0, description="Filter by transaction")
    from_date: Optional[date] = Field(None, description="Filter from this date")
    to_date: Optional[date] = Field(None, description="Filter to this date")
    search: Optional[str] = Field(
        None, max_length=100, description="Search in description"
    )
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum amount")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum amount")
    manual_only: Optional[bool] = Field(
        None, description="If true, only show manual payments (transaction_id is null)"
    )

    class Config:
        from_attributes = True


# Response DTOs


class ContactInPaymentResponse(BaseModel):
    """Minimal contact info in payment response"""

    id: int
    name: str
    phone: str
    type: str

    class Config:
        from_attributes = True


class TransactionInPaymentResponse(BaseModel):
    """Minimal transaction info in payment response"""

    id: int
    transaction_number: str
    transaction_date: date
    type: str
    total_amount: Decimal

    class Config:
        from_attributes = True


class ManualPaymentResponse(BaseModel):
    """Response model for manual payment with all details"""

    id: int
    payment_date: date
    type: Literal['income', 'expense']
    category: Optional[str] = None
    amount: Decimal
    payment_method: PaymentMethod
    contact: Optional[ContactInPaymentResponse] = None
    transaction: Optional[TransactionInPaymentResponse] = None
    description: Optional[str] = None
    reference_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ManualPaymentListItemResponse(BaseModel):
    """Lighter response model for payment list view"""

    id: int
    payment_date: date
    type: Literal['income', 'expense']
    category: Optional[str] = None
    amount: Decimal
    payment_method: PaymentMethod
    contact: Optional[ContactInPaymentResponse] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Summary/Report DTOs


class PaymentSummaryResponse(BaseModel):
    """Summary response for financial overview"""

    total_amount: Decimal = Field(..., description="Total amount of all payments (spends + earnings)")
    total_spends: Decimal = Field(..., description="Total amount spent (expenses)")
    total_earnings: Decimal = Field(..., description="Total amount earned (income)")
    payment_count: int = Field(..., description="Number of payment transactions")
    
    # Breakdown by category
    category_breakdown: dict[str, Decimal] = Field(
        ..., description="Breakdown of amounts by category"
    )

    class Config:
        from_attributes = True


class SuggestedCategoriesResponse(BaseModel):
    """Response with suggested payment categories"""

    income_categories: List[str] = Field(..., description="List of suggested income categories")
    expense_categories: List[str] = Field(..., description="List of suggested expense categories")

    class Config:
        from_attributes = True

