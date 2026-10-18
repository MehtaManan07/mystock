"""
Shared helpers for the assistant services.

``owned_thread`` is the single place every service resolves a thread, and it
is load-bearing for privacy: *not finding* a thread and *not being allowed to
see it* raise the identical ``NotFoundError``, so the API cannot be used to
discover whether someone else's conversation exists.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError

from ..models import DEFAULT_THREAD_TITLE, MAX_TITLE_LENGTH, AssistantThread


def derive_title(text: str) -> str:
    """A thread's title is its opening question, trimmed to fit."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return DEFAULT_THREAD_TITLE
    if len(cleaned) <= MAX_TITLE_LENGTH:
        return cleaned
    return cleaned[: MAX_TITLE_LENGTH - 1].rstrip() + "\u2026"


def owned_thread(db: Session, thread_id: int, user_id: int) -> AssistantThread:
    thread = db.execute(
        select(AssistantThread).where(
            AssistantThread.id == thread_id,
            AssistantThread.user_id == user_id,
            AssistantThread.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if thread is None:
        raise NotFoundError("Conversation", thread_id)
    return thread
