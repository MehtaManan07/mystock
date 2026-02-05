"""Company Settings Model"""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.core.db.base import BaseModel


class CompanySettings(BaseModel):
    """
    Company settings model for storing seller/company information.
    Used for invoice generation and other company-wide settings.
    Only one active record should exist at a time.
    """

    __tablename__ = "company_settings"

    # Company Information
    company_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Mayur Agency"
    )

    # Seller Information
    seller_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Rajen Mehta"
    )
    
    seller_phone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="9930597995"
    )
    
    seller_email: Mapped[str] = mapped_column(
        String(255), nullable=False, default="rajenmehta4567@gmail.com"
    )
    
    seller_gstin: Mapped[str] = mapped_column(
        String(15), nullable=False, default="24ABHFM6157G1Z7"
    )

    # Company Address (3 lines for better formatting)
    company_address_line1: Mapped[str] = mapped_column(
        String(255), nullable=False, default="0"
    )
    
    company_address_line2: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Manhar Lodge, Opp. Vegetable Market"
    )
    
    company_address_line3: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Rajkot, Gujarat - 360001"
    )

    # Terms and Conditions (stored as newline-separated text)
    terms_and_conditions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            "Subject to our home Jurisdiction.\n"
            "Our Responsibility Ceases as soon as goods leaves our Premises.\n"
            "Goods once sold will not taken back.\n"
            "Delivery Ex-Premises."
        ),
    )

    # Only one active settings record should exist
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    def __repr__(self) -> str:
        return f"<CompanySettings(id={self.id}, company='{self.company_name}', active={self.is_active})>"
