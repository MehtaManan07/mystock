"""SQLite-compatible initial migration

Revision ID: 0001_sqlite_initial
Revises: 
Create Date: 2026-01-11

This migration is compatible with both SQLite and PostgreSQL.
Key differences from PostgreSQL version:
- Uses CURRENT_TIMESTAMP instead of now()
- ENUMs stored as VARCHAR (native_enum=False in models)
- No PostgreSQL-specific types
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_sqlite_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with SQLite-compatible syntax."""
    
    # Contacts table
    op.create_table('contacts',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('gstin', sa.String(length=15), nullable=True),
        # ENUM as VARCHAR for SQLite compatibility
        sa.Column('type', sa.String(length=20), server_default='customer', nullable=False),
        sa.Column('balance', sa.Numeric(precision=15, scale=2), server_default='0.0', nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        # Use CURRENT_TIMESTAMP for SQLite compatibility
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contacts_gstin'), 'contacts', ['gstin'], unique=False)
    op.create_index(op.f('ix_contacts_name'), 'contacts', ['name'], unique=False)
    
    # Container table
    op.create_table('container',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_container_name'), 'container', ['name'], unique=True)
    
    # Product table
    op.create_table('product',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('size', sa.String(length=255), nullable=False),
        sa.Column('packing', sa.String(length=255), nullable=False),
        sa.Column('default_sale_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('default_purchase_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_product_name_size_packing', 'product', ['name', 'size', 'packing'], unique=True)
    
    # Users table
    op.create_table('users',
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='JOBBER', nullable=False),
        sa.Column('contact_info', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    
    # Container-Product junction table
    op.create_table('container_product',
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['container_id'], ['container.id'], name='fk_container_product_container_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='fk_container_product_product_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_container_product_unique', 'container_product', ['container_id', 'product_id'], unique=True)
    
    # Inventory Log table
    op.create_table('inventory_log',
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['container_id'], ['container.id'], name='fk_inventory_log_container_id'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='fk_inventory_log_product_id'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Transactions table
    op.create_table('transactions',
        sa.Column('transaction_number', sa.String(length=50), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=15, scale=2), server_default='0.0', nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=15, scale=2), server_default='0.0', nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(precision=15, scale=2), server_default='0.0', nullable=False),
        sa.Column('payment_status', sa.String(length=20), server_default='unpaid', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('invoice_url', sa.String(length=500), nullable=True),
        sa.Column('invoice_checksum', sa.String(length=64), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], name='fk_transaction_contact_id'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transaction_date', 'transactions', ['transaction_date'], unique=False)
    op.create_index('idx_transaction_invoice_url', 'transactions', ['invoice_url'], unique=False)
    op.create_index('idx_transaction_number', 'transactions', ['transaction_number'], unique=True)
    op.create_index('idx_transaction_type_status', 'transactions', ['type', 'payment_status'], unique=False)
    op.create_index(op.f('ix_transactions_invoice_url'), 'transactions', ['invoice_url'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_date'), 'transactions', ['transaction_date'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_number'), 'transactions', ['transaction_number'], unique=True)
    
    # Payments table
    op.create_table('payments',
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('payment_method', sa.String(length=20), nullable=False),
        sa.Column('type', sa.String(length=16), server_default='expense', nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], name='fk_payment_contact_id'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name='fk_payment_transaction_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_payment_type', 'payments', ['type'], unique=False)
    op.create_index(op.f('ix_payments_category'), 'payments', ['category'], unique=False)
    op.create_index(op.f('ix_payments_payment_date'), 'payments', ['payment_date'], unique=False)
    op.create_index(op.f('ix_payments_type'), 'payments', ['type'], unique=False)
    
    # Transaction Items table
    op.create_table('transaction_items',
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('line_total', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['container_id'], ['container.id'], name='fk_transaction_item_container_id'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='fk_transaction_item_product_id'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name='fk_transaction_item_transaction_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transaction_item_transaction_product', 'transaction_items', ['transaction_id', 'product_id'], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_index('idx_transaction_item_transaction_product', table_name='transaction_items')
    op.drop_table('transaction_items')
    
    op.drop_index(op.f('ix_payments_type'), table_name='payments')
    op.drop_index(op.f('ix_payments_payment_date'), table_name='payments')
    op.drop_index(op.f('ix_payments_category'), table_name='payments')
    op.drop_index('idx_payment_type', table_name='payments')
    op.drop_table('payments')
    
    op.drop_index(op.f('ix_transactions_transaction_number'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_transaction_date'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_invoice_url'), table_name='transactions')
    op.drop_index('idx_transaction_type_status', table_name='transactions')
    op.drop_index('idx_transaction_number', table_name='transactions')
    op.drop_index('idx_transaction_invoice_url', table_name='transactions')
    op.drop_index('idx_transaction_date', table_name='transactions')
    op.drop_table('transactions')
    
    op.drop_table('inventory_log')
    
    op.drop_index('idx_container_product_unique', table_name='container_product')
    op.drop_table('container_product')
    
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    
    op.drop_index('idx_product_name_size_packing', table_name='product')
    op.drop_table('product')
    
    op.drop_index(op.f('ix_container_name'), table_name='container')
    op.drop_table('container')
    
    op.drop_index(op.f('ix_contacts_name'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_gstin'), table_name='contacts')
    op.drop_table('contacts')
