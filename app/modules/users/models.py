import enum
from sqlalchemy import String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.core.db.base import BaseModel


class Role(str, enum.Enum):
    """User role enum - equivalent to TypeORM Role enum"""

    ADMIN = "ADMIN"
    STAFF = "STAFF"
    JOBBER = "JOBBER"
    MANAGER = "MANAGER"


class User(BaseModel):
    """
    User model - equivalent to TypeORM User entity.
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        # Note: In SQLAlchemy, "select: false" behavior is typically handled
        # at the query level using deferred() or by explicitly selecting columns
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[Role] = mapped_column(
        SQLEnum(
            Role,
            name="users_role_enum",
            native_enum=False,
        ),
        nullable=False,
        default=Role.JOBBER,
        server_default=Role.JOBBER.value,
    )

    contact_info: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, username='{self.username}', role={self.role.value})>"
        )
