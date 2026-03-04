"""add performance indexes for inventory_log and transactions

Revision ID: 0011_add_performance_indexes
Revises: 0010_convert_quantities_to_items
Create Date: 2026-03-04

Adds:
  - inventory_log: indexes on product_id, container_id, timestamp
  - transactions: index on contact_id
"""
from typing import Sequence, Union

from alembic import op


revision: str = '0011_add_performance_indexes'
down_revision: Union[str, Sequence[str], None] = '0010_convert_quantities_to_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('idx_inventory_log_product_id', 'inventory_log', ['product_id'])
    op.create_index('idx_inventory_log_container_id', 'inventory_log', ['container_id'])
    op.create_index('idx_inventory_log_timestamp', 'inventory_log', ['timestamp'])
    op.create_index('idx_transaction_contact_id', 'transactions', ['contact_id'])


def downgrade() -> None:
    op.drop_index('idx_transaction_contact_id', table_name='transactions')
    op.drop_index('idx_inventory_log_timestamp', table_name='inventory_log')
    op.drop_index('idx_inventory_log_container_id', table_name='inventory_log')
    op.drop_index('idx_inventory_log_product_id', table_name='inventory_log')
