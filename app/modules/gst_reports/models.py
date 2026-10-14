from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseModel


class GstReview(BaseModel):
    """Append-only reporting snapshots and documented accountant reviews."""

    __tablename__ = "gst_reviews"
    __table_args__ = (UniqueConstraint("source_key", "revision", name="uq_gst_review_revision"),)

    source_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    verified: Mapped[bool] = mapped_column(nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
