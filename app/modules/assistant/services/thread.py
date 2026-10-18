"""Conversations: create, list, fetch, rename and soft-delete a thread."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError

from ..models import DEFAULT_THREAD_TITLE, AssistantThread
from ._common import derive_title, owned_thread


class ThreadService:
    """Conversations."""

    @staticmethod
    async def create(user_id: int, title: Optional[str] = None) -> AssistantThread:
        def _create(db: Session) -> AssistantThread:
            thread = AssistantThread(
                user_id=user_id,
                title=derive_title(title) if title else DEFAULT_THREAD_TITLE,
            )
            db.add(thread)
            db.flush()
            db.refresh(thread)
            return thread

        return await run_db(_create)

    @staticmethod
    async def list_for_user(user_id: int) -> List[AssistantThread]:
        def _list(db: Session) -> List[AssistantThread]:
            return list(
                db.execute(
                    select(AssistantThread)
                    .where(
                        AssistantThread.user_id == user_id,
                        AssistantThread.deleted_at.is_(None),
                    )
                    .order_by(desc(AssistantThread.updated_at))
                )
                .scalars()
                .all()
            )

        return await run_db(_list)

    @staticmethod
    async def get(user_id: int, thread_id: int) -> AssistantThread:
        def _get(db: Session) -> AssistantThread:
            return owned_thread(db, thread_id, user_id)

        return await run_db(_get)

    @staticmethod
    async def get_with_messages(user_id: int, thread_id: int) -> AssistantThread:
        """
        The whole conversation in one query.

        Messages are eagerly loaded on purpose: ``run_db`` closes the session
        before this returns, so a lazy relationship would raise the moment the
        router touched it.
        """

        def _get(db: Session) -> AssistantThread:
            thread = db.execute(
                select(AssistantThread)
                .where(
                    AssistantThread.id == thread_id,
                    AssistantThread.user_id == user_id,
                    AssistantThread.deleted_at.is_(None),
                )
                .options(selectinload(AssistantThread.messages))
            ).scalar_one_or_none()
            if thread is None:
                raise NotFoundError("Conversation", thread_id)
            return thread

        return await run_db(_get)

    @staticmethod
    async def rename(user_id: int, thread_id: int, title: str) -> AssistantThread:
        def _rename(db: Session) -> AssistantThread:
            thread = owned_thread(db, thread_id, user_id)
            thread.title = derive_title(title)
            db.flush()
            db.refresh(thread)
            return thread

        return await run_db(_rename)

    @staticmethod
    async def soft_delete(user_id: int, thread_id: int) -> None:
        def _delete(db: Session) -> None:
            thread = owned_thread(db, thread_id, user_id)
            thread.deleted_at = func.now()
            db.flush()

        await run_db(_delete)
