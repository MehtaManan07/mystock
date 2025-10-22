import enum
from datetime import date
from decimal import Decimal
from sqlalchemy import (
    String,
    Date,
    Numeric,
    Integer,
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
    from app.modules.products.models import Product
    from app.modules.containers.models import Container


class TransactionType(str, enum.Enum):
    """Transaction type enum"""

    sale = "sale"
    purchase = "purchase"


class PaymentStatus(str, enum.Enum):
    """Payment status enum"""

    paid = "paid"
    partial = "partial"
    unpaid = "unpaid"


class PaymentMethod(str, enum.Enum):
    """Payment method enum"""

    cash = "cash"
    bank_transfer = "bank_transfer"
    upi = "upi"
    cheque = "cheque"
    other = "other"


class Transaction(BaseModel):
    """
    Transaction model for managing sales and purchases.
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "transactions"

    # Indexes for performance
    __table_args__ = (
        Index("idx_transaction_number", "transaction_number", unique=True),
        Index("idx_transaction_contact_id", "contact_id"),
        Index("idx_transaction_date", "transaction_date"),
        Index("idx_transaction_type_status", "type", "payment_status"),
    )

    transaction_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType, name="transaction_type_enum"),
        nullable=False,
    )

    # Foreign Keys
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", name="fk_transaction_contact_id"),
        nullable=False,
        index=True,
    )

    # Financial fields - all with 15 digits total, 2 decimal places
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0.0,
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0.0,
    )

    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    payment_status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, name="payment_status_enum"),
        nullable=False,
        default=PaymentStatus.unpaid,
        server_default=PaymentStatus.unpaid.value,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", lazy="joined")

    items: Mapped[list["TransactionItem"]] = relationship(
        "TransactionItem",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, number='{self.transaction_number}', type={self.type.value}, total={self.total_amount})>"


class TransactionItem(BaseModel):
    """
    Transaction item model - line items in a transaction.
    Links transactions to products with quantities and pricing.
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "transaction_items"

    # Indexes for performance
    __table_args__ = (
        Index("idx_transaction_item_transaction_id", "transaction_id"),
        Index("idx_transaction_item_product_id", "product_id"),
        Index(
            "idx_transaction_item_transaction_product",
            "transaction_id",
            "product_id",
        ),
    )

    # Foreign Keys
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE", name="fk_transaction_item_transaction_id"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", name="fk_transaction_item_product_id"),
        nullable=False,
        index=True,
    )

    container_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("container.id", name="fk_transaction_item_container_id"),
        nullable=True,
        default=None,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="items"
    )

    product: Mapped["Product"] = relationship("Product", lazy="joined")

    container: Mapped[Optional["Container"]] = relationship(
        "Container", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<TransactionItem(id={self.id}, transaction_id={self.transaction_id}, product_id={self.product_id}, qty={self.quantity}, total={self.line_total})>"


class Payment(BaseModel):
    """
    Payment model - tracks payments made against transactions.
    Supports partial payments and multiple payment methods.
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "payments"

    # Indexes for performance
    __table_args__ = (
        Index("idx_payment_transaction_id", "transaction_id"),
        Index("idx_payment_date", "payment_date"),
    )

    # Foreign Keys
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE", name="fk_payment_transaction_id"),
        nullable=False,
        index=True,
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

    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="payments"
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount}, method={self.payment_method.value})>"

