"""Record one row per agent tool call for performance observability."""
from alembic import op
import sqlalchemy as sa


revision = "0020_assistant_tool_calls"
down_revision = "0019_pdf_invoice_numbering"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_tool_calls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("output_chars", sa.Integer(), nullable=True),
        sa.Column("output_preview", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Plain correlation handles, not foreign keys: telemetry must outlive the
        # threads it describes and never block their cleanup.
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_assistant_tool_calls_name_created",
        "assistant_tool_calls",
        ["tool_name", "created_at"],
    )
    op.create_index(
        "ix_assistant_tool_calls_created",
        "assistant_tool_calls",
        ["created_at"],
    )


def downgrade():
    op.drop_index("ix_assistant_tool_calls_created", table_name="assistant_tool_calls")
    op.drop_index("ix_assistant_tool_calls_name_created", table_name="assistant_tool_calls")
    op.drop_table("assistant_tool_calls")
