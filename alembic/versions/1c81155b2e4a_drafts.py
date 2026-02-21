"""drafts

Revision ID: 1c81155b2e4a
Revises: 0007_add_product_image
Create Date: 2026-02-21 21:04:02.639938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c81155b2e4a'
down_revision: Union[str, Sequence[str], None] = '0007_add_product_image'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add drafts table."""
    # Create drafts table
    op.create_table('drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    with op.batch_alter_table('drafts', schema=None) as batch_op:
        batch_op.create_index('ix_drafts_id', ['id'], unique=False)
        batch_op.create_index('ix_drafts_type', ['type'], unique=False)
        batch_op.create_index('ix_drafts_user_id', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - remove drafts table."""
    with op.batch_alter_table('drafts', schema=None) as batch_op:
        batch_op.drop_index('ix_drafts_user_id')
        batch_op.drop_index('ix_drafts_type')
        batch_op.drop_index('ix_drafts_id')

    op.drop_table('drafts')

