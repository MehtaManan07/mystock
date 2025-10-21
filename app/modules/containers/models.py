import enum
from sqlalchemy import String, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.db.base import BaseModel

if TYPE_CHECKING:
    from app.modules.container_products.models import ContainerProduct
    from app.modules.inventory_logs.models import InventoryLog


class ContainerType(str, enum.Enum):
    """Container type enum - equivalent to TypeORM ContainerType enum"""

    single = "single"
    mixed = "mixed"


class Container(BaseModel):
    """
    Container model - equivalent to TypeORM Container entity.
    """

    __tablename__ = "container"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    type: Mapped[ContainerType] = mapped_column(
        SQLEnum(ContainerType, name="container_type_enum"), nullable=False
    )

    # Relationships
    contents: Mapped[list["ContainerProduct"]] = relationship(
        "ContainerProduct", back_populates="container", cascade="all, delete-orphan"
    )

    logs: Mapped[list["InventoryLog"]] = relationship(
        "InventoryLog", back_populates="container"
    )

    def __repr__(self) -> str:
        return f"<Container(id={self.id}, name='{self.name}', type={self.type.value})>"
