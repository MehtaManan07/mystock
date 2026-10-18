"""
Runs: one attempt by the agent to answer.

*Concluding a run is a single transaction.* Writing the assistant's reply and
closing the run happen together or not at all. A client that sees the run end
and immediately reloads will always find the message; there is no window where
the run looks finished but the reply has not landed. Getting this wrong is the
bug that makes an answer vanish on refresh, and it is invisible in testing
because the window is milliseconds wide on a local database.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError

from ..models import (
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    MessageRole,
    RunStatus,
)
from ._common import owned_thread

logger = logging.getLogger(__name__)

# Shown when a run dies for a reason the user cannot act on. The real
# exception is logged, never stored and never sent to the browser.
GENERIC_ERROR_TEXT = "Something went wrong and I couldn't finish that."


class RunService:
    """Attempts by the agent to answer."""

    @staticmethod
    async def open(user_id: int, thread_id: int) -> AssistantRun:
        """
        Begin a run, provided the thread is not already busy.

        The uniqueness is enforced by a partial unique index, not by looking
        first and inserting second -- two requests arriving together would
        both pass that check. We catch the integrity error and report it as a
        conflict.
        """

        def _open(db: Session) -> AssistantRun:
            owned_thread(db, thread_id, user_id)
            run = AssistantRun(
                thread_id=thread_id,
                user_id=user_id,
                status=RunStatus.RUNNING,
            )
            db.add(run)
            try:
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                raise ConflictError(
                    "This conversation is already working on something"
                ) from exc
            # No refresh: the caller reads only id/thread_id/user_id, all known
            # once the insert has flushed. Re-selecting the row would be a
            # second round trip for columns nobody reads.
            return run

        return await run_db(_open)

    @staticmethod
    async def get(user_id: int, run_id: int) -> AssistantRun:
        def _get(db: Session) -> AssistantRun:
            run = db.execute(
                select(AssistantRun).where(
                    AssistantRun.id == run_id, AssistantRun.user_id == user_id
                )
            ).scalar_one_or_none()
            if run is None:
                raise NotFoundError("Run", run_id)
            return run

        return await run_db(_get)

    @staticmethod
    async def active_for_thread(user_id: int, thread_id: int) -> Optional[AssistantRun]:
        def _active(db: Session) -> Optional[AssistantRun]:
            owned_thread(db, thread_id, user_id)
            return db.execute(
                select(AssistantRun).where(
                    AssistantRun.thread_id == thread_id,
                    AssistantRun.status == RunStatus.RUNNING,
                )
            ).scalar_one_or_none()

        return await run_db(_active)

    # -- concluding -------------------------------------------------------

    @staticmethod
    async def complete(
        run_id: int, content: str, widget: Optional[dict] = None
    ) -> Optional[AssistantMessage]:
        return await RunService._conclude(run_id, RunStatus.COMPLETED, content, widget)

    @staticmethod
    async def cancel(run_id: int, content: str = "") -> Optional[AssistantMessage]:
        """
        Stop a run but keep whatever it already said.

        Those tokens were paid for and the user watched them appear; throwing
        them away on reload would be worse than keeping a partial answer.
        """
        return await RunService._conclude(run_id, RunStatus.CANCELLED, content, None)

    @staticmethod
    async def fail(
        run_id: int,
        error_code: str,
        error_message: str = GENERIC_ERROR_TEXT,
        content: str = "",
    ) -> Optional[AssistantMessage]:
        return await RunService._conclude(
            run_id,
            RunStatus.FAILED,
            content or error_message,
            None,
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    async def _conclude(
        run_id: int,
        status: str,
        content: str,
        widget: Optional[dict],
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[AssistantMessage]:
        """
        Close the run and save its reply in one transaction.

        Either both land or neither does. That is what lets the caller emit
        the terminal event immediately afterwards without racing a client
        that reloads the instant it arrives.

        A run that produced nothing at all -- no text, no widget -- writes no
        message. An empty assistant bubble is worse than no bubble.
        """

        def _finish(db: Session) -> Optional[AssistantMessage]:
            run = db.execute(
                select(AssistantRun).where(AssistantRun.id == run_id)
            ).scalar_one_or_none()
            if run is None:
                logger.warning("Concluding unknown run %s", run_id)
                return None
            if run.is_terminal:
                # Already closed. Cancel racing a natural finish is normal.
                return None

            message: Optional[AssistantMessage] = None
            if content or widget:
                thread = db.execute(
                    select(AssistantThread).where(
                        AssistantThread.id == run.thread_id,
                        AssistantThread.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()

                if thread is None:
                    # The user deleted the conversation mid-run. Nothing to
                    # attach the reply to, and that is not an error.
                    logger.info(
                        "Thread %s gone before run %s concluded; discarding reply",
                        run.thread_id,
                        run_id,
                    )
                else:
                    message = AssistantMessage(
                        thread_id=run.thread_id,
                        role=MessageRole.ASSISTANT,
                        content=content,
                        widget=widget,
                    )
                    db.add(message)
                    thread.updated_at = func.now()
                    db.flush()
                    run.message_id = message.id

            run.status = status
            run.error_code = error_code
            run.error_message = error_message
            run.finished_at = func.now()

            db.flush()
            # No refresh: every caller discards this return value, so there is
            # nothing to re-select for.
            return message

        return await run_db(_finish)

    @staticmethod
    async def reconcile_stale_runs() -> int:
        """
        Close runs orphaned by a restart.

        The queues and task that served a run live in process memory, so a
        process that dies takes them with it while the row stays `running`
        forever -- blocking the thread, because of the partial unique index.
        Anything still `running` at startup had no survivor, so it is closed.

        Safe only while a single worker serves the app. With two workers this
        would shoot down runs belonging to the other one.
        """

        def _reconcile(db: Session) -> int:
            # One bulk UPDATE rather than loading every running row and
            # closing it in a Python loop. Startup is usually cheap either
            # way, but there is no reason to hydrate objects we only overwrite.
            result = db.execute(
                update(AssistantRun)
                .where(AssistantRun.status == RunStatus.RUNNING)
                .values(
                    status=RunStatus.INTERRUPTED,
                    error_code="interrupted",
                    error_message="The server restarted before this finished.",
                    finished_at=func.now(),
                )
            )
            return result.rowcount or 0

        count = await run_db(_reconcile)
        if count:
            logger.warning("Closed %d run(s) orphaned by a restart", count)
        return count
