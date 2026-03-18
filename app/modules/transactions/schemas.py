"""
Transaction DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from .models import TransactionType, PaymentStatus, ProductDetailsDisplayMode, TaxType
from app.modules.payments.models import PaymentMethod


# Request DTOs


class TransactionItemCreate(BaseModel):
    """DTO for creating a transaction item (line item)"""

    product_id: int = Field(..., gt=0, description="Product ID")
    container_id: Optional[int] = Field(
        None, gt=0, description="Container ID (required for sales)"
    )
    quantity: int = Field(..., gt=0, description="Quantity in items")
    unit_price: Decimal = Field(
        ..., ge=0, description="Unit price per item (can be 0 for free items)"
    )

    class Config:
        from_attributes = True


class CreateTransactionDto(BaseModel):
    """Base DTO for creating a transaction (sale or purchase)"""

    transaction_date: date = Field(..., description="Date of transaction")
    contact_id: int = Field(..., gt=0, description="Contact ID (customer or supplier)")
    items: List[TransactionItemCreate] = Field(
        ..., min_length=1, description="Transaction items (at least one)"
    )

    tax_amount: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Tax/GST amount"
    )
    discount_amount: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Discount amount"
    )

    # Payment fields (if paying at time of transaction)
    paid_amount: Decimal = Field(
        default=Decimal("0.0"), ge=0, description="Amount paid immediately"
    )
    payment_method: Optional[PaymentMethod] = Field(
        None, description="Payment method (required if paid_amount > 0)"
    )
    payment_reference: Optional[str] = Field(
        None, max_length=100, description="Payment reference number"
    )

    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")

    # Product details display mode for invoice generation
    product_details_display_mode: ProductDetailsDisplayMode = Field(
        default=ProductDetailsDisplayMode.customer_sku,
        description="Display mode for product details in invoice (customer_sku, company_sku, or product_name)"
    )

    # Tax type: igst (inter-state) or cgst_sgst (intra-state)
    tax_type: Optional[TaxType] = Field(
        None,
        description="Tax type: 'igst' for inter-state or 'cgst_sgst' for intra-state. Auto-determined from GSTIN if not provided."
    )

    class Config:
        from_attributes = True


class CreateSaleDto(CreateTransactionDto):
    """DTO for creating a sale transaction"""

    # Inherits all fields from CreateTransactionDto
    # Sale-specific validation will be done in service layer:
    # - Contact must be customer or both
    # - All items must have container_id specified
    # - Container must have sufficient stock
    pass


class CreatePurchaseDto(CreateTransactionDto):
    """DTO for creating a purchase transaction"""

    # Inherits all fields from CreateTransactionDto
    # Purchase-specific validation will be done in service layer:
    # - Contact must be supplier or both
    # - Items must have container_id (destination)
    pass


class CreatePaymentDto(BaseModel):
    """DTO for recording a payment against an existing transaction"""

    payment_date: date = Field(..., description="Date of payment")
    amount: Decimal = Field(..., gt=0, description="Payment amount (must be positive)")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    reference_number: Optional[str] = Field(
        None, max_length=100, description="Payment reference number"
    )
    notes: Optional[str] = Field(None, max_length=1000, description="Payment notes")

    class Config:
        from_attributes = True


class TransactionFilterDto(BaseModel):
    """DTO for filtering transactions"""

    type: Optional[TransactionType] = Field(
        None, description="Filter by transaction type"
    )
    payment_status: Optional[PaymentStatus] = Field(
        None, description="Filter by payment status"
    )
    contact_id: Optional[int] = Field(None, gt=0, description="Filter by contact")
    from_date: Optional[date] = Field(None, description="Filter from this date")
    to_date: Optional[date] = Field(None, description="Filter to this date")
    search: Optional[str] = Field(
        None, max_length=100, description="Search in transaction number or notes"
    )

    class Config:
        from_attributes = True


# Response DTOs - Nested models for relationships


class ProductInTransactionResponse(BaseModel):
    """Minimal product info in transaction response"""

    id: int
    name: str
    size: str
    packing: str

    class Config:
        from_attributes = True


class ContainerInTransactionResponse(BaseModel):
    """Minimal container info in transaction response"""

    id: int
    name: str
    type: str

    class Config:
        from_attributes = True


class ContactInTransactionResponse(BaseModel):
    """Contact info in transaction response"""

    id: int
    name: str
    phone: str
    type: str
    balance: Decimal
    gstin: Optional[str] = None

    class Config:
        from_attributes = True


class TransactionItemResponse(BaseModel):
    """Response model for transaction item with product and container details"""

    id: int
    product: ProductInTransactionResponse
    container: Optional[ContainerInTransactionResponse] = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    """Response model for payment"""

    id: int
    payment_date: date
    amount: Decimal
    payment_method: PaymentMethod
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    """Full response model for transaction with all details"""

    id: int
    transaction_number: str
    transaction_date: date
    type: TransactionType
    contact: ContactInTransactionResponse

    items: List[TransactionItemResponse]

    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    payment_status: PaymentStatus

    # Tax type and split amounts
    tax_type: TaxType = Field(default=TaxType.igst, description="Tax type: igst or cgst_sgst")
    cgst_amount: Optional[Decimal] = Field(None, description="CGST amount (tax_amount/2 if intra-state)")
    sgst_amount: Optional[Decimal] = Field(None, description="SGST amount (tax_amount/2 if intra-state)")

    # Computed field
    balance_due: Decimal = Field(..., description="Total amount - paid amount")

    notes: Optional[str] = None

    # Invoice fields
    invoice_url: Optional[str] = Field(
        None, description="Cloud storage URL of generated invoice PDF"
    )
    invoice_checksum: Optional[str] = Field(
        None, description="MD5 checksum of invoice PDF"
    )

    # Product details display mode
    product_details_display_mode: ProductDetailsDisplayMode = Field(
        ..., description="Display mode for product details in invoice"
    )

    payments: List[PaymentResponse]

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    @model_validator(mode='after')
    def compute_tax_split(self) -> 'TransactionResponse':
        """Compute CGST/SGST amounts from tax_amount when tax_type is cgst_sgst."""
        if self.tax_type == TaxType.cgst_sgst and self.tax_amount > 0:
            half = (self.tax_amount / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.cgst_amount = half
            self.sgst_amount = self.tax_amount - half
        return self

    class Config:
        from_attributes = True


class TransactionListItemResponse(BaseModel):
    """Lighter response model for transaction list view"""

    id: int
    transaction_number: str
    transaction_date: date
    type: TransactionType
    contact: ContactInTransactionResponse
    total_amount: Decimal
    paid_amount: Decimal
    payment_status: PaymentStatus
    balance_due: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


# Summary/Report DTOs


class TransactionSummaryResponse(BaseModel):
    """Summary response for financial overview"""

    total_sales: Decimal = Field(..., description="Total sales amount")
    total_purchases: Decimal = Field(..., description="Total purchases amount")
    total_sales_paid: Decimal = Field(..., description="Total sales paid amount")
    total_purchases_paid: Decimal = Field(
        ..., description="Total purchases paid amount"
    )

    outstanding_receivables: Decimal = Field(
        ..., description="Amount customers owe (unpaid sales)"
    )
    outstanding_payables: Decimal = Field(
        ..., description="Amount we owe suppliers (unpaid purchases)"
    )

    total_sales_count: int = Field(..., description="Number of sales transactions")
    total_purchases_count: int = Field(
        ..., description="Number of purchase transactions"
    )

    class Config:
        from_attributes = True


class OutstandingTransactionResponse(BaseModel):
    """Response for outstanding (unpaid/partial) transactions"""

    id: int
    transaction_number: str
    transaction_date: date
    type: TransactionType
    contact: ContactInTransactionResponse
    total_amount: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    payment_status: PaymentStatus
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceMetadataResponse(BaseModel):
    """Response for invoice metadata (optimized endpoint)"""

    transaction_id: int
    transaction_number: str
    invoice_url: Optional[str] = Field(None, description="Cloud storage URL of invoice PDF")
    invoice_checksum: Optional[str] = Field(
        None, description="MD5 checksum for integrity verification"
    )

    class Config:
        from_attributes = True
