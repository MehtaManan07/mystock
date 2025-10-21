from datetime import datetime
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from app.core.db import BaseModel

if TYPE_CHECKING:
    from app.modules.products.models import Product
    from app.modules.containers.models import Container


class InventoryLog(BaseModel):
    """
    InventoryLog model - equivalent to TypeORM InventoryLog entity.
    Tracks inventory changes for products in containers.
    Uses eager loading for product and container relationships.
    """

    __tablename__ = "inventory_log"

    # Foreign Keys
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", name="fk_inventory_log_product_id"), nullable=False
    )

    container_id: Mapped[int] = mapped_column(
        ForeignKey("container.id", name="fk_inventory_log_container_id"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    action: Mapped[str] = mapped_column(String(255), nullable=False)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    # Relationships with eager loading (equivalent to TypeORM's { eager: true })
    product: Mapped["Product"] = relationship(
        "Product", back_populates="logs", lazy="joined"  # This enables eager loading
    )

    container: Mapped["Container"] = relationship(
        "Container", back_populates="logs", lazy="joined"  # This enables eager loading
    )

    def __repr__(self) -> str:
        return f"<InventoryLog(id={self.id}, product_id={self.product_id}, container_id={self.container_id}, action='{self.action}', quantity={self.quantity})>"
