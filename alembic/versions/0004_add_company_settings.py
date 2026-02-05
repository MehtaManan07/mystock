"""Add company_settings table

Revision ID: 0004_add_company_settings
Revises: 0003_add_last_verified_at
Create Date: 2026-02-06

Creates the company_settings table for storing seller/company information
used in invoice generation and other company-wide configurations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_add_company_settings'
down_revision: Union[str, Sequence[str], None] = '0003_add_last_verified_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create company_settings table with default values."""
    # Create the table
    op.create_table(
        'company_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('seller_name', sa.String(length=255), nullable=False),
        sa.Column('seller_phone', sa.String(length=50), nullable=False),
        sa.Column('seller_email', sa.String(length=255), nullable=False),
        sa.Column('seller_gstin', sa.String(length=15), nullable=False),
        sa.Column('company_address_line1', sa.String(length=255), nullable=False),
        sa.Column('company_address_line2', sa.String(length=255), nullable=False),
        sa.Column('company_address_line3', sa.String(length=255), nullable=False),
        sa.Column('terms_and_conditions', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on is_active
    op.create_index('ix_company_settings_is_active', 'company_settings', ['is_active'])
    
    # Insert default company settings
    op.execute("""
        INSERT INTO company_settings (
            company_name,
            seller_name,
            seller_phone,
            seller_email,
            seller_gstin,
            company_address_line1,
            company_address_line2,
            company_address_line3,
            terms_and_conditions,
            is_active
        ) VALUES (
            'Mayur Agency',
            'Manan Mehta',
            '9328483009',
            'mananmehtar@gmail.com',
            '24ABHFM6157G1Z7',
            '0',
            'Manhar Lodge, Opp. Vegetable Market',
            'Rajkot, Karnataka - 360001',
            'Subject to our home Jurisdiction.
Our Responsibility Ceases as soon as goods leaves our Premises.
Goods once sold will not taken back.
Delivery Ex-Premises.',
            1
        )
    """)


def downgrade() -> None:
    """Drop company_settings table."""
    op.drop_index('ix_company_settings_is_active', table_name='company_settings')
    op.drop_table('company_settings')
