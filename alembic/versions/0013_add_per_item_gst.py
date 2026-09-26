"""add per-item GST rate and HSN

Revision ID: 0013_per_item_gst
Revises: 0012_add_tax_type
Create Date: 2026-09-01

Adds per-product GST rate and HSN code, plus per-line tax snapshots on
transaction items, so invoices can apply the rate applicable to each item
instead of a single blended rate across the whole invoice.

All columns are nullable and additive; existing rows keep working through the
legacy path (transaction-level tax_amount).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013_per_item_gst'
down_revision: Union[str, Sequence[str], None] = '0012_add_tax_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add GST rate/HSN to products and tax snapshots to transaction items."""
    op.add_column('product', sa.Column('gst_rate', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('product', sa.Column('hsn_code', sa.String(length=20), nullable=True))

    op.add_column('transaction_items', sa.Column('tax_rate', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('transaction_items', sa.Column('tax_amount', sa.Numeric(precision=15, scale=2), nullable=True))


def downgrade() -> None:
    """Remove per-item GST columns."""
    op.drop_column('transaction_items', 'tax_amount')
    op.drop_column('transaction_items', 'tax_rate')
    op.drop_column('product', 'hsn_code')
    op.drop_column('product', 'gst_rate')
