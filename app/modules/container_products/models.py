from sqlalchemy import Integer, ForeignKey, Index, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.db import BaseModel

if TYPE_CHECKING:
    from app.modules.containers.models import Container
    from app.modules.products.models import Product


class ContainerProduct(BaseModel):
    """
    ContainerProduct model - junction table between Container and Product.
    Equivalent to TypeORM ContainerProduct entity.
    Has a composite unique index on (container_id, product_id).
    """

    __tablename__ = "container_product"

    # Composite unique index on container_id and product_id
    __table_args__ = (
        Index(
            "idx_container_product_unique", "container_id", "product_id", unique=True
        ),
    )

    # Foreign Keys
    container_id: Mapped[int] = mapped_column(
        ForeignKey(
            "container.id", ondelete="CASCADE", name="fk_container_product_container_id"
        ),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "product.id", ondelete="CASCADE", name="fk_container_product_product_id"
        ),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    container: Mapped["Container"] = relationship(
        "Container", back_populates="contents"
    )

    product: Mapped["Product"] = relationship("Product", back_populates="containers")

    def __repr__(self) -> str:
        # Handle detached instances gracefully to avoid DetachedInstanceError
        try:
            insp = inspect(self)
            if insp.detached:
                return f"<ContainerProduct(detached)>"
            return f"<ContainerProduct(id={self.id}, container_id={self.container_id}, product_id={self.product_id}, quantity={self.quantity})>"
        except Exception:
            return f"<ContainerProduct(unknown state)>"
