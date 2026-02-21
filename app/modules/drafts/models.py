"""
Draft Transaction Models - Store incomplete transactions
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, func, JSON
from app.core.db.base import Base
import enum


class DraftType(str, enum.Enum):
    """Type of draft transaction"""
    SALE = "sale"
    PURCHASE = "purchase"


class Draft(Base):
    """
    Draft model for saving incomplete transactions.
    Stores the form state as JSON for later retrieval.
    """
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # User who created the draft
    type = Column(SQLEnum(DraftType), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # e.g., "Draft sale - 2/21/2026"
    data = Column(JSON, nullable=False)  # JSON object of form state
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
