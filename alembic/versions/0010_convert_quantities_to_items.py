"""convert container_product quantities from packs to items

Revision ID: 0010_convert_quantities_to_items
Revises: 0009_add_quantity_items_to_transaction_items
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_convert_quantities_to_items'
down_revision: Union[str, Sequence[str], None] = '0009_add_quantity_items_to_transaction_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert all container_product quantities from packs to items
    
    For products with packing > 1: quantity_items = quantity_packs * packing
    For products with packing = 1: quantity_items = quantity_packs (no change)
    """
    
    # Update quantities: multiply by packing for products where packing > 1
    op.execute("""
        UPDATE container_product
        SET quantity = quantity * (
            SELECT CAST(p.packing AS INTEGER)
            FROM product p
            WHERE p.id = container_product.product_id
            AND p.packing GLOB '[0-9]*'
            AND CAST(p.packing AS INTEGER) > 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM product p
            WHERE p.id = container_product.product_id
            AND p.packing GLOB '[0-9]*'
            AND CAST(p.packing AS INTEGER) > 1
        )
        AND deleted_at IS NULL
    """)
    
    print("✓ Converted container_product quantities from packs to items")


def downgrade() -> None:
    """Revert container_product quantities from items back to packs
    
    WARNING: This may result in data loss due to rounding if quantities 
    were not evenly divisible by packing size.
    """
    
    # Revert quantities: divide by packing for products where packing > 1
    op.execute("""
        UPDATE container_product
        SET quantity = quantity / (
            SELECT CAST(p.packing AS INTEGER)
            FROM product p
            WHERE p.id = container_product.product_id
            AND p.packing GLOB '[0-9]*'
            AND CAST(p.packing AS INTEGER) > 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM product p
            WHERE p.id = container_product.product_id
            AND p.packing GLOB '[0-9]*'
            AND CAST(p.packing AS INTEGER) > 1
        )
        AND deleted_at IS NULL
    """)
    
    print("✓ Reverted container_product quantities from items back to packs")
