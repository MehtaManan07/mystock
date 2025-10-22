import enum
from sqlalchemy import String, Enum as SQLEnum, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class ContactType(str, enum.Enum):
    """Contact type enum"""

    customer = "customer"
    supplier = "supplier"
    both = "both"


class Contact(BaseModel):
    """
    Contact model for managing customers and suppliers.
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "contacts"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    phone: Mapped[str] = mapped_column(String(50), nullable=False)

    address: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, default=None
    )

    gstin: Mapped[Optional[str]] = mapped_column(
        String(15), nullable=True, default=None, index=True
    )

    type: Mapped[ContactType] = mapped_column(
        SQLEnum(
            ContactType,
            name="contacts_type_enum",
        ),
        nullable=False,
        default=ContactType.customer,
        server_default=ContactType.customer.value,
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name='{self.name}', type={self.type.value}, balance={self.balance})>"
