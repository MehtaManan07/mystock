"""Persist PDF invoice customer links, including unambiguous historical matches."""
from alembic import op
import sqlalchemy as sa


revision = "0018_pdf_invoice_customer"
down_revision = "0017_assistant"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pdf_invoices", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_pdf_invoices_customer_id", "pdf_invoices", "contacts", ["customer_id"], ["id"]
    )
    op.create_index("ix_pdf_invoices_customer_id", "pdf_invoices", ["customer_id"])
    # Resolve identity once, not on reads. Keep uncertain historical links null.
    op.execute(sa.text("""
        WITH matches AS (
            SELECT p.id, MIN(c.id) AS customer_id
            FROM pdf_invoices p
            JOIN contacts c ON (
                CASE WHEN NULLIF(TRIM(p.customer_gstin), '') IS NOT NULL
                    THEN UPPER(TRIM(c.gstin)) = UPPER(TRIM(p.customer_gstin))
                    ELSE LOWER(TRIM(c.name)) = LOWER(TRIM(p.customer_name))
                         AND NULLIF(TRIM(p.customer_name), '') IS NOT NULL
                END
            )
            WHERE p.customer_id IS NULL AND c.deleted_at IS NULL
            GROUP BY p.id, p.customer_gstin
            HAVING COUNT(*) = 1
                AND MIN(c.type) IN ('customer', 'both')
                AND (NULLIF(TRIM(p.customer_gstin), '') IS NOT NULL
                     OR MAX(NULLIF(TRIM(c.gstin), '')) IS NULL)
        )
        UPDATE pdf_invoices
        SET customer_id = matches.customer_id
        FROM matches
        WHERE pdf_invoices.id = matches.id AND pdf_invoices.customer_id IS NULL
    """))


def downgrade():
    op.drop_index("ix_pdf_invoices_customer_id", table_name="pdf_invoices")
    op.drop_constraint("fk_pdf_invoices_customer_id", "pdf_invoices", type_="foreignkey")
    op.drop_column("pdf_invoices", "customer_id")
