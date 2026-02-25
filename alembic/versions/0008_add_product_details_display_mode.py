"""add product details display mode

Revision ID: 0008_add_product_details_display_mode
Revises: 686341f1afff
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_add_product_details_display_mode'
down_revision: Union[str, Sequence[str], None] = '686341f1afff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add product_details_display_mode column to transactions table"""
    # Add the new column with default value
    op.add_column('transactions', 
        sa.Column('product_details_display_mode', 
                  sa.String(length=20), 
                  nullable=False, 
                  server_default='customer_sku'))


def downgrade() -> None:
    """Remove product_details_display_mode column from transactions table"""
    op.drop_column('transactions', 'product_details_display_mode')
