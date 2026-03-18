"""add tax_type column to transactions

Revision ID: 0012_add_tax_type
Revises: 0011_add_performance_indexes
Create Date: 2026-03-18

Adds tax_type column (igst or cgst_sgst) to transactions table.
Backfills existing rows based on seller/buyer GSTIN state codes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012_add_tax_type'
down_revision: Union[str, Sequence[str], None] = '0011_add_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tax_type column and backfill based on GSTIN state codes."""
    # Add the new column with default 'igst'
    op.add_column('transactions',
        sa.Column('tax_type', sa.String(length=10), nullable=False, server_default='igst'))

    # Backfill: compare seller GSTIN state code (first 2 chars) with buyer GSTIN
    # Seller GSTIN starts with '24' (Gujarat)
    # If buyer GSTIN also starts with '24' -> cgst_sgst (intra-state)
    conn = op.get_bind()

    # Get seller GSTIN from company_settings
    result = conn.execute(
        sa.text("SELECT seller_gstin FROM company_settings WHERE is_active = 1 LIMIT 1")
    )
    row = result.fetchone()
    if row and row[0]:
        seller_state_code = row[0][:2]

        # Update transactions where buyer (contact) has same state code -> cgst_sgst
        conn.execute(sa.text("""
            UPDATE transactions
            SET tax_type = 'cgst_sgst'
            WHERE contact_id IN (
                SELECT id FROM contacts
                WHERE gstin IS NOT NULL
                AND length(gstin) >= 2
                AND substr(gstin, 1, 2) = :seller_state
            )
        """), {"seller_state": seller_state_code})


def downgrade() -> None:
    """Remove tax_type column."""
    op.drop_column('transactions', 'tax_type')
