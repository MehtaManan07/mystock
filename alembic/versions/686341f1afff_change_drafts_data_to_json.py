"""change drafts data to json

Revision ID: 686341f1afff
Revises: 1c81155b2e4a
Create Date: 2026-02-21 21:16:02.579800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '686341f1afff'
down_revision: Union[str, Sequence[str], None] = '1c81155b2e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change drafts.data from TEXT to JSON"""
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    with op.batch_alter_table('drafts', schema=None) as batch_op:
        batch_op.alter_column('data',
                              existing_type=sa.Text(),
                              type_=sa.JSON(),
                              existing_nullable=False)


def downgrade() -> None:
    """Change drafts.data from JSON back to TEXT"""
    with op.batch_alter_table('drafts', schema=None) as batch_op:
        batch_op.alter_column('data',
                              existing_type=sa.JSON(),
                              type_=sa.Text(),
                              existing_nullable=False)
