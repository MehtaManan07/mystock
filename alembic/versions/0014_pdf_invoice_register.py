"""Add a standalone PDF invoice register without stock or balance effects."""
from alembic import op
import sqlalchemy as sa


revision = "0014_pdf_invoice_register"
down_revision = "0013_per_item_gst"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pdf_invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("financial_year", sa.String(9), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_gstin", sa.String(15)),
        sa.Column("customer_address", sa.String(500)),
        sa.Column("customer_phone", sa.String(50)),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False),
        sa.Column("cgst", sa.Numeric(15, 2), nullable=False),
        sa.Column("sgst", sa.Numeric(15, 2), nullable=False),
        sa.Column("igst", sa.Numeric(15, 2), nullable=False),
        sa.Column("round_off", sa.Numeric(5, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("line_items", sa.JSON()),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("pdf_sha256", sa.String(64), nullable=False),
        sa.Column("metadata_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("upload_status", sa.String(20), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("financial_year", "invoice_number", name="uq_pdf_invoice_number_year"),
        sa.UniqueConstraint("pdf_sha256", name="uq_pdf_invoice_sha256"),
    )
    op.create_index("ix_pdf_invoices_invoice_date", "pdf_invoices", ["invoice_date"])


def downgrade():
    op.drop_index("ix_pdf_invoices_invoice_date", table_name="pdf_invoices")
    op.drop_table("pdf_invoices")
