"""Assistant threads, messages and runs.

Creates the three tables the assistant needs. Nothing is backfilled; existing
data is untouched.

Note what is absent: there is no table for the agent's thoughts. Status lines
and tool-call notices live only for the duration of a run, so that reopening a
conversation shows exactly what streaming showed.

All three tables follow the house ``BaseModel`` shape: an autoincrement
integer primary key and the shared ``created_at`` / ``updated_at`` /
``deleted_at`` columns. Message order is the ``id`` itself -- a thread is never
written concurrently, so the sequence is the conversation order.
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_assistant"
down_revision = "0016_gst_reporting"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_threads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", name="fk_assistant_thread_user_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
    )
    op.create_index(
        "ix_assistant_threads_user_updated",
        "assistant_threads",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey(
                "assistant_threads.id",
                name="fk_assistant_message_thread_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("widget", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_assistant_messages_thread_id",
        "assistant_messages",
        ["thread_id", "id"],
    )

    op.create_table(
        "assistant_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey(
                "assistant_threads.id",
                name="fk_assistant_run_thread_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", name="fk_assistant_run_user_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey(
                "assistant_messages.id",
                name="fk_assistant_run_message_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_assistant_runs_thread_created",
        "assistant_runs",
        ["thread_id", "created_at"],
    )
    # One live run per thread, enforced in the database rather than by a
    # check-then-insert race: the partial index only covers running rows.
    op.create_index(
        "uq_assistant_runs_active_per_thread",
        "assistant_runs",
        ["thread_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade():
    op.drop_index(
        "uq_assistant_runs_active_per_thread", table_name="assistant_runs"
    )
    op.drop_index("ix_assistant_runs_thread_created", table_name="assistant_runs")
    op.drop_table("assistant_runs")

    op.drop_index("ix_assistant_messages_thread_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")

    op.drop_index("ix_assistant_threads_user_updated", table_name="assistant_threads")
    op.drop_table("assistant_threads")
