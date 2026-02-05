"""VendorProductSku model for managing vendor-specific SKU mappings."""

from sqlalchemy import String, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.db.base import BaseModel

if TYPE_CHECKING:
    from app.modules.products.models import Product
    from app.modules.contacts.models import Contact


class VendorProductSku(BaseModel):
    """
    VendorProductSku model for storing vendor-specific SKUs for products.
    Each vendor can have their own SKU for a product.
    One SKU per product per vendor (enforced by unique constraint).
    """

    __tablename__ = "vendor_product_sku"

    __table_args__ = (
        UniqueConstraint("product_id", "vendor_id", name="uq_vendor_product_sku_product_vendor"),
        Index("ix_vendor_product_sku_product_id", "product_id"),
        Index("ix_vendor_product_sku_vendor_id", "vendor_id"),
    )

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id", ondelete="CASCADE"), nullable=False
    )

    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )

    vendor_sku: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="vendor_skus")
    vendor: Mapped["Contact"] = relationship("Contact")

    def __repr__(self) -> str:
        return f"<VendorProductSku(id={self.id}, product_id={self.product_id}, vendor_id={self.vendor_id}, vendor_sku='{self.vendor_sku}')>"
