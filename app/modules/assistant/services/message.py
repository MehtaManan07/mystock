"""Durable turns: the messages that survive the run and a page reload."""

from __future__ import annotations

from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db.engine import run_db

from ..models import DEFAULT_THREAD_TITLE, AssistantMessage, MessageRole
from ._common import derive_title, owned_thread


class MessageService:
    """Durable turns."""

    @staticmethod
    async def append_user_message(
        user_id: int, thread_id: int, content: str
    ) -> AssistantMessage:
        """
        Record what the user said.

        Also names the thread, if it is still unnamed -- the opening question
        is a better label than anything we could generate, and it costs no
        extra round trip because we are already writing in this transaction.
        """

        def _append(db: Session) -> AssistantMessage:
            thread = owned_thread(db, thread_id, user_id)

            message = AssistantMessage(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=content,
            )
            db.add(message)

            if thread.title == DEFAULT_THREAD_TITLE:
                thread.title = derive_title(content)
            # Adding a child row does not touch the parent, and the thread
            # list is ordered by this column.
            thread.updated_at = func.now()

            db.flush()
            db.refresh(message)
            return message

        return await run_db(_append)

    @staticmethod
    async def list_for_thread(user_id: int, thread_id: int) -> List[AssistantMessage]:
        def _list(db: Session) -> List[AssistantMessage]:
            owned_thread(db, thread_id, user_id)
            return list(
                db.execute(
                    select(AssistantMessage)
                    .where(AssistantMessage.thread_id == thread_id)
                    .order_by(AssistantMessage.id)
                )
                .scalars()
                .all()
            )

        return await run_db(_list)
