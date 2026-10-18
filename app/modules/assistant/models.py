"""
Assistant persistence models.

Three tables, matching what the domain actually has:

    assistant_threads    one conversation
    assistant_messages   what you will still see tomorrow
    assistant_runs       one attempt by the agent to answer

WHAT IS *NOT* HERE, DELIBERATELY
--------------------------------
The agent's visible thinking -- status lines, tool calls -- is never written
down. It exists only while the run is live. That is what makes a thread read
identically whether you watched it stream or opened it an hour later; if we
persisted thoughts, a refresh would silently change the transcript.

The live plumbing of a run (its ``asyncio.Queue`` and ``Task``) is likewise
absent, because a running coroutine cannot be a row. The row here records what
a run *was*; ``runtime.py`` holds what a run *is doing*. That split is also why
``status`` can be stale after a crash -- see ``RunStatus.INTERRUPTED``.

IDS AND ORDERING
----------------
All three tables use ``BaseModel``: the house autoincrement integer primary
key and the shared ``created_at`` / ``updated_at`` / ``deleted_at`` columns,
exactly like every other model in the app.

Message order is the ``id`` itself. The sequence hands out increasing values,
and a thread is never written to concurrently -- the partial unique index on
``assistant_runs`` allows only one live run per thread, so the user turn and
the assistant turn are always written in order. ``created_at`` cannot do this
job: Postgres ``now()`` is transaction-scoped, so two rows written in one
transaction share a timestamp exactly. ``created_at`` is for display, ``id``
is for ordering.

The streaming ``message_id`` the client sees in ``text_message_start`` is a
separate, per-stream correlation handle generated in ``agent.py``; it is not
this primary key and never needs to be.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import BaseModel

DEFAULT_THREAD_TITLE = "New chat"
MAX_TITLE_LENGTH = 120


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"

    ALL = (USER, ASSISTANT)


class RunStatus:
    """
    Statuses are plain strings, not a Postgres ENUM.

    Adding a value to a PG enum needs a migration and, historically, could not
    run inside a transaction. This set will grow as the agent does, and a
    ``VARCHAR`` keeps that free.
    """

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    # Process died mid-run. Nobody will ever finish this one, so it is closed
    # at startup rather than left to look live forever.
    INTERRUPTED = "interrupted"

    ALL = (RUNNING, COMPLETED, CANCELLED, FAILED, INTERRUPTED)
    TERMINAL = (COMPLETED, CANCELLED, FAILED, INTERRUPTED)


class AssistantThread(BaseModel):
    """One conversation. Soft-deleted so history is recoverable."""

    __tablename__ = "assistant_threads"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_assistant_thread_user_id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(MAX_TITLE_LENGTH), nullable=False, default=DEFAULT_THREAD_TITLE
    )

    messages: Mapped[list["AssistantMessage"]] = relationship(
        "AssistantMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="AssistantMessage.id",
    )
    runs: Mapped[list["AssistantRun"]] = relationship(
        "AssistantRun",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="AssistantRun.id",
    )

    __table_args__ = (
        # The thread list: this user's threads, most recently touched first.
        Index("ix_assistant_threads_user_updated", "user_id", "updated_at"),
    )


class AssistantMessage(BaseModel):
    """
    A durable turn in the conversation.

    Only two roles exist, and that is load-bearing: it is what stops anyone
    from quietly persisting the agent's thoughts as messages and replaying
    them into the model later.
    """

    __tablename__ = "assistant_messages"

    thread_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "assistant_threads.id",
            name="fk_assistant_message_thread_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The rendered widget, if this turn produced one. Carries its own decided
    # state, so a confirmation cannot be acted on twice.
    widget: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    thread: Mapped["AssistantThread"] = relationship(
        "AssistantThread", back_populates="messages"
    )

    __table_args__ = (
        # Fetch a thread's messages in order; `id` is the order.
        Index("ix_assistant_messages_thread_id", "thread_id", "id"),
    )


class AssistantRun(BaseModel):
    """
    One attempt by the agent to answer. Rows outlive the process; the queues
    and tasks that actually serve them do not.
    """

    __tablename__ = "assistant_runs"

    thread_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "assistant_threads.id",
            name="fk_assistant_run_thread_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_assistant_run_user_id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RunStatus.RUNNING
    )

    # Populated on failure. `error_code` is safe to show a user; the raw
    # exception is logged, never stored, and never sent to the browser.
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The reply this run produced, if it produced one. Lets us prove the
    # message was written before the run was closed.
    message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey(
            "assistant_messages.id",
            name="fk_assistant_run_message_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True, default=None
    )

    thread: Mapped["AssistantThread"] = relationship(
        "AssistantThread", back_populates="runs"
    )

    __table_args__ = (
        Index("ix_assistant_runs_thread_created", "thread_id", "created_at"),
        # Two jobs, one index. It makes "one live run per thread" a database
        # guarantee rather than a check-then-act race between two requests,
        # and it is also the index startup reconciliation scans to find runs
        # a dead process left marked `running`.
        Index(
            "uq_assistant_runs_active_per_thread",
            "thread_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in RunStatus.TERMINAL
