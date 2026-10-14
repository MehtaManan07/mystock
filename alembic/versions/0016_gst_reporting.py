"""Add append-only GST reporting reviews; no accounting data is backfilled."""
from alembic import op
import sqlalchemy as sa


revision = "0016_gst_reporting"
down_revision = "0015_company_bank_details"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gst_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source_key", "revision", name="uq_gst_review_revision"),
    )
    op.create_index("ix_gst_reviews_source_key", "gst_reviews", ["source_key"])
    op.create_index("ix_gst_reviews_document_date", "gst_reviews", ["document_date"])


def downgrade():
    op.drop_index("ix_gst_reviews_document_date", table_name="gst_reviews")
    op.drop_index("ix_gst_reviews_source_key", table_name="gst_reviews")
    op.drop_table("gst_reviews")
