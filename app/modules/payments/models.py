import enum
from datetime import date
from decimal import Decimal
from sqlalchemy import (
    String,
    Date,
    Numeric,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from app.core.db.base import BaseModel

if TYPE_CHECKING:
    from app.modules.contacts.models import Contact
    from app.modules.transactions.models import Transaction


class PaymentMethod(str, enum.Enum):
    """Payment method enum"""

    cash = "cash"
    bank_transfer = "bank_transfer"
    upi = "upi"
    cheque = "cheque"
    card = "card"
    other = "other"


# Suggested payment categories (not enforced, just helpful suggestions for users)
SUGGESTED_PAYMENT_CATEGORIES = [
    # Expenses/Spends
    "rent",
    "electricity",
    "water",
    "internet",
    "phone",
    "salary",
    "maintenance",
    "transport",
    "office_supplies",
    "professional_fees",  # Lawyers, accountants, consultants
    "insurance",
    "taxes",
    "bank_charges",
    "transaction_payment",  # Auto-set for transaction-linked payments
    # Income/Earnings
    "sales_income",
    "service_income",
    "interest_income",
    "commission_income",
    "rental_income",
    "other_income",
    # Other
    "other",
]

# Categories that represent income/earnings (all others are considered expenses/spends)
INCOME_CATEGORIES = {
    "sales_income",
    "service_income",
    "interest_income",
    "commission_income",
    "rental_income",
    "other_income",
}


class Payment(BaseModel):
    """
    Unified Payment model - tracks both:
    1. Payments against transactions (sales/purchases) - when transaction_id is set
    2. Manual payments (rent, electricity, salaries, etc.) - when transaction_id is null
    
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "payments"

    # Indexes for performance
    __table_args__ = (
        Index("idx_payment_date", "payment_date"),
        Index("idx_payment_category", "category"),
        Index("idx_payment_type", "type"),
    )

    # Foreign Keys
    transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "transactions.id", ondelete="CASCADE", name="fk_payment_transaction_id"
        ),
        nullable=True,  # Null for manual payments not linked to transactions
        default=None,
    )

    contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contacts.id", name="fk_payment_contact_id"),
        nullable=True,  # Optional contact reference
        default=None,
    )

    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )

    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod, name="payment_method_enum"),
        nullable=False,
    )

    # Explicit type for classifying as income or expense (string)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True, server_default='expense')
    __table_args__ = (
        Index("idx_payment_type", "type"),
    )

    # Category - free text field (users can add their own categories)
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None, index=True
    )

    # Description (optional for transaction payments, required for manual payments via validation)
    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, default=None
    )

    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # Relationships
    transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", back_populates="payments"
    )
    
    contact: Mapped[Optional["Contact"]] = relationship("Contact", lazy="joined")

    @property
    def is_manual_payment(self) -> bool:
        """Returns True if this is a manual payment (not linked to a transaction)"""
        return self.transaction_id is None

    def __repr__(self) -> str:
        if self.transaction_id:
            return f"<Payment(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount}, method={self.payment_method.value})>"
        else:
            return f"<Payment(id={self.id}, category={self.category or 'N/A'}, amount={self.amount}, manual=True)>"

