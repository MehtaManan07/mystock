"""Drop notes column from payments table

Revision ID: 0002_drop_payments_notes
Revises: 0001_sqlite_initial
Create Date: 2026-01-13

Removes the redundant 'notes' column from the payments table.
Users should use the 'description' field instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_drop_payments_notes'
down_revision: Union[str, Sequence[str], None] = '0001_sqlite_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the notes column from payments table."""
    # SQLite doesn't support DROP COLUMN directly before version 3.35.0
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('payments') as batch_op:
        batch_op.drop_column('notes')


def downgrade() -> None:
    """Re-add the notes column to payments table."""
    with op.batch_alter_table('payments') as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
