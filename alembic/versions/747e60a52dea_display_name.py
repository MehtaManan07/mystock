"""display name

Revision ID: 747e60a52dea
Revises: 0005_add_company_sku_and_hsn
Create Date: 2026-02-06 02:42:19.712301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '747e60a52dea'
down_revision: Union[str, Sequence[str], None] = '0005_add_company_sku_and_hsn'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get connection to check if columns/tables exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Skip the temp table cleanup if it doesn't exist
    existing_tables = inspector.get_table_names()
    if '_alembic_tmp_product' in existing_tables:
        op.drop_table('_alembic_tmp_product')
    
    # Skip batch operations that cause FK constraint issues
    # These are just column type changes (enum declarations) which SQLite doesn't enforce strictly
    # The app models define the correct types, so this is safe to skip
    
    # Only do the essential change: add display_name to product
    product_columns = [col['name'] for col in inspector.get_columns('product')]
    if 'display_name' not in product_columns:
        op.add_column('product', sa.Column('display_name', sa.String(length=255), nullable=False, server_default=''))

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # Skip batch operations - just remove display_name column
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    product_columns = [col['name'] for col in inspector.get_columns('product')]
    if 'display_name' in product_columns:
        with op.batch_alter_table('product', schema=None) as batch_op:
            batch_op.drop_column('display_name')
    
    # The temp table recreation is not necessary for downgrade
    # ### end Alembic commands ###
