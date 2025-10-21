from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.db import BaseModel

if TYPE_CHECKING:
    from app.modules.container_products.models import ContainerProduct
    from app.modules.inventory_logs.models import InventoryLog


class Product(BaseModel):
    """
    Product model - equivalent to TypeORM Product entity.
    Has a composite unique index on (name, size, packing).
    """

    __tablename__ = "product"

    # Composite unique index on name, size, packing
    __table_args__ = (
        Index("idx_product_name_size_packing", "name", "size", "packing", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    size: Mapped[str] = mapped_column(String(255), nullable=False)

    packing: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    containers: Mapped[list["ContainerProduct"]] = relationship(
        "ContainerProduct", back_populates="product", cascade="all, delete-orphan"
    )

    logs: Mapped[list["InventoryLog"]] = relationship(
        "InventoryLog", back_populates="product"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}', size='{self.size}', packing='{self.packing}')>"
