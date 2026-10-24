"""Persisting tool-call telemetry: one row per invocation, best-effort."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.db.engine import run_db

from ..models import AssistantToolCall

logger = logging.getLogger("assistant.tools")

# Kept in step with the stdout preview budget, but roomier because a stored row
# is worth a little more context than a scrolling log line.
OUTPUT_PREVIEW_CHARS = 500


class ToolCallLogService:
    """Append-only telemetry writes. Never raises into a live run."""

    @staticmethod
    async def record(
        *,
        tool_name: str,
        inputs: Optional[dict],
        ok: bool,
        duration_ms: int,
        output_chars: Optional[int] = None,
        output_preview: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        thread_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Write one tool-call row.

        Telemetry must never degrade the thing it measures: if the insert fails
        (DB blip, shutdown race), the failure is swallowed with a warning and the
        agent's answer is unaffected. A lost performance row is cheaper than a
        broken reply.
        """

        def _insert(db: Session) -> None:
            db.add(
                AssistantToolCall(
                    tool_name=tool_name,
                    inputs=inputs,
                    ok=ok,
                    duration_ms=duration_ms,
                    output_chars=output_chars,
                    output_preview=(
                        output_preview[:OUTPUT_PREVIEW_CHARS]
                        if output_preview is not None
                        else None
                    ),
                    error_type=error_type,
                    error_message=error_message,
                    thread_id=thread_id,
                    user_id=user_id,
                )
            )
            db.commit()

        try:
            await run_db(_insert)
        except Exception:  # noqa: BLE001 - telemetry must not break a run
            logger.warning(
                "Failed to persist tool-call record for %s", tool_name, exc_info=True
            )
