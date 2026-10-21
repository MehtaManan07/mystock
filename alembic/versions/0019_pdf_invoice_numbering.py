"""Reserve new PDF numbers in the shared sales sequence without changing issued bills."""
from alembic import op
import sqlalchemy as sa


revision = "0019_pdf_invoice_numbering"
down_revision = "0018_pdf_invoice_customer"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pdf_invoice_number_reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("invoice_number", sa.String(50), nullable=False, unique=True),
        sa.Column("spec_sha256", sa.String(64), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )


def downgrade():
    # Reserved numbers must not be recycled during an accidental rollback.
    raise RuntimeError("Invoice number reservations must be retained; downgrade requires a reviewed recovery plan")
