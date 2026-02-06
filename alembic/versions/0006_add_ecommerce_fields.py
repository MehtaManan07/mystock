"""add ecommerce fields

Revision ID: 0006_add_ecommerce_fields
Revises: 747e60a52dea
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_add_ecommerce_fields'
down_revision: Union[str, Sequence[str], None] = '747e60a52dea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get connection to check if columns exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    product_columns = [col['name'] for col in inspector.get_columns('product')]
    
    # Add description column (Text, nullable)
    if 'description' not in product_columns:
        op.add_column('product', sa.Column('description', sa.Text(), nullable=True))
    
    # Add mrp column (Numeric, nullable)
    if 'mrp' not in product_columns:
        op.add_column('product', sa.Column('mrp', sa.Numeric(precision=15, scale=2), nullable=True))
    
    # Add tags column (JSON, nullable)
    if 'tags' not in product_columns:
        op.add_column('product', sa.Column('tags', sa.JSON(), nullable=True))
    
    # Add product_type column (String(255), nullable)
    if 'product_type' not in product_columns:
        op.add_column('product', sa.Column('product_type', sa.String(length=255), nullable=True))
    
    # Add dimensions column (JSON, nullable)
    if 'dimensions' not in product_columns:
        op.add_column('product', sa.Column('dimensions', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    product_columns = [col['name'] for col in inspector.get_columns('product')]
    
    # Remove columns if they exist
    with op.batch_alter_table('product', schema=None) as batch_op:
        if 'dimensions' in product_columns:
            batch_op.drop_column('dimensions')
        if 'product_type' in product_columns:
            batch_op.drop_column('product_type')
        if 'tags' in product_columns:
            batch_op.drop_column('tags')
        if 'mrp' in product_columns:
            batch_op.drop_column('mrp')
        if 'description' in product_columns:
            batch_op.drop_column('description')
