"""Add product_image table

Revision ID: 0007_add_product_image
Revises: 0006_add_ecommerce_fields
Create Date: 2026-02-07

Creates the product_image table for storing product images (Google Drive references).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_add_product_image"
down_revision: Union[str, Sequence[str], None] = "0006_add_ecommerce_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create product_image table."""
    op.create_table(
        "product_image",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("drive_file_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("thumb_url", sa.String(length=1024), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_product_image_product_id"), "product_image", ["product_id"], unique=False)
    op.create_index(op.f("ix_product_image_drive_file_id"), "product_image", ["drive_file_id"], unique=False)


def downgrade() -> None:
    """Drop product_image table."""
    op.drop_index(op.f("ix_product_image_drive_file_id"), table_name="product_image")
    op.drop_index(op.f("ix_product_image_product_id"), table_name="product_image")
    op.drop_table("product_image")
