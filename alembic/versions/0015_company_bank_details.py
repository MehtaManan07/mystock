"""Add optional company bank details for invoice payment instructions."""
from alembic import op
import sqlalchemy as sa


revision = "0015_company_bank_details"
down_revision = "0014_pdf_invoice_register"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_settings", sa.Column("bank_name", sa.String(255), nullable=True))
    op.add_column("company_settings", sa.Column("bank_account_number", sa.String(50), nullable=True))
    op.add_column("company_settings", sa.Column("bank_branch", sa.String(255), nullable=True))
    op.add_column("company_settings", sa.Column("bank_ifsc", sa.String(11), nullable=True))


def downgrade():
    with op.batch_alter_table("company_settings") as batch:
        batch.drop_column("bank_ifsc")
        batch.drop_column("bank_branch")
        batch.drop_column("bank_account_number")
        batch.drop_column("bank_name")
