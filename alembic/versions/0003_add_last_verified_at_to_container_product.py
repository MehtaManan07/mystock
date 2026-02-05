"""Add last_verified_at column to container_product table

Revision ID: 0003_add_last_verified_at
Revises: 0002_drop_payments_notes
Create Date: 2026-02-05

Adds a timestamp column to track when a product-container location
was last verified/confirmed by staff. This helps indicate data freshness.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_last_verified_at'
down_revision: Union[str, Sequence[str], None] = '0002_drop_payments_notes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_verified_at column to container_product table."""
    with op.batch_alter_table('container_product') as batch_op:
        batch_op.add_column(
            sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    """Remove last_verified_at column from container_product table."""
    with op.batch_alter_table('container_product') as batch_op:
        batch_op.drop_column('last_verified_at')
