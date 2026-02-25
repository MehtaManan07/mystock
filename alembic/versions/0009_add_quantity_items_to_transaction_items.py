"""add quantity_items to transaction_items

Revision ID: 0009_add_quantity_items_to_transaction_items
Revises: 0008_add_product_details_display_mode
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_add_quantity_items_to_transaction_items'
down_revision: Union[str, Sequence[str], None] = '0008_add_product_details_display_mode'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quantity_items column to transaction_items table and backfill data"""
    
    # Check if column already exists, if not add it
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('transaction_items')]
    
    if 'quantity_items' not in columns:
        # Add the new column (nullable initially for backfill)
        op.add_column('transaction_items', 
            sa.Column('quantity_items', sa.Integer(), nullable=True))
    
    # Backfill existing records: quantity_items = quantity * packing
    # SQLite syntax: use subquery in SET clause
    op.execute("""
        UPDATE transaction_items 
        SET quantity_items = quantity * (
            SELECT CAST(packing AS INTEGER)
            FROM product
            WHERE product.id = transaction_items.product_id
            AND packing GLOB '[0-9]*'
        )
        WHERE quantity_items IS NULL
        AND EXISTS (
            SELECT 1
            FROM product
            WHERE product.id = transaction_items.product_id
            AND packing GLOB '[0-9]*'
        )
    """)
    
    # For non-numeric packing, assume 1:1 (each pack = 1 item)
    op.execute("""
        UPDATE transaction_items 
        SET quantity_items = quantity
        WHERE quantity_items IS NULL
    """)


def downgrade() -> None:
    """Remove quantity_items column from transaction_items table"""
    op.drop_column('transaction_items', 'quantity_items')
