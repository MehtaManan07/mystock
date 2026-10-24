"""
Central tool-call logging.

Every tool the agent runs passes through one callback handler, so there is a
single uniform record of *what* was called, with *which arguments*, *what it
returned*, *how long it took*, and *whether it failed*. This is the only place
tool performance is observed; the tools themselves stay ignorant of it.

WHY A CALLBACK, NOT A WRAPPER
-----------------------------
LangChain propagates callbacks down every runnable in a graph run, so attaching
one handler to the run's config captures *every* tool invocation without
touching a single tool, the registry, or the adapter. The handler sees the real
argument dict and the real return value (verified against a compiled graph), so
the log is ground truth, not a reconstruction.

WHY HERE AND NOT IN THE ADAPTER
-------------------------------
The adapter is UI-facing and deliberately drops tool arguments and results from
the browser stream. This is the opposite concern: a private, server-side record
for *us* to see how the tools behave. Keeping it separate means the UI contract
and the operational log never constrain each other.

WHAT IS LOGGED
--------------
Arguments are small and bounded, so they are logged in full. Results can be
large (row dumps), so only their size and a short single-line preview are
logged -- enough to eyeball correctness without drowning the log. Everything
goes to the ``assistant.tools`` logger; point that logger at a file or raise its
level independently of the rest of the app if you want a dedicated tool trace.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Coroutine, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler

logger = logging.getLogger("assistant.tools")

# Background persistence tasks are kept here so the event loop holds a strong
# reference until they finish -- asyncio only weakly references tasks, so a
# fire-and-forget coroutine would otherwise be garbage-collected mid-flight.
_PENDING: set[asyncio.Task] = set()

# Results are summarised, not dumped: enough to confirm the shape of an answer
# without replaying a 30-row list into the log on every call.
_OUTPUT_PREVIEW_CHARS = 160
# Arguments are small, but a pathological search string shouldn't blow up a log
# line either.
_ARGS_MAX_CHARS = 300


def _one_line(value: Any, limit: int) -> str:
    """Collapse to a single line and cap length, so one record is one line."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _as_text(output: Any) -> str:
    """The string a tool returned, whether raw or wrapped in a message object."""
    content = getattr(output, "content", output)
    return content if isinstance(content, str) else str(content)


class ToolCallLogger(AsyncCallbackHandler):
    """
    One record per tool call: start args, then outcome with duration.

    A fresh instance is used per run so its in-flight timing map never collides
    across concurrent conversations. Start times are keyed by the call's
    ``run_id`` -- the same id the adapter uses as the tool-call id -- so a start
    and its end always pair up even when tools run in parallel in one turn.
    """

    def __init__(
        self, *, thread_id: Optional[int] = None, user_id: Optional[int] = None
    ) -> None:
        self._thread_id = thread_id
        self._user_id = user_id
        self._started: dict[UUID, tuple[str, float, Optional[dict]]] = {}

    def _context(self) -> str:
        bits = []
        if self._thread_id is not None:
            bits.append(f"thread={self._thread_id}")
        if self._user_id is not None:
            bits.append(f"user={self._user_id}")
        return (" [" + " ".join(bits) + "]") if bits else ""

    async def on_tool_start(
        self,
        serialized: Optional[dict],
        input_str: str,
        *,
        run_id: UUID,
        inputs: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
        self._started[run_id] = (name, time.perf_counter(), inputs)
        args = inputs if inputs is not None else input_str
        logger.info(
            "TOOL start  %s%s args=%s",
            name,
            self._context(),
            _one_line(args, _ARGS_MAX_CHARS),
        )

    async def on_tool_end(
        self, output: Any, *, run_id: UUID, **kwargs: Any
    ) -> None:
        name, elapsed_ms, inputs = self._finish(run_id)
        text = _as_text(output)
        logger.info(
            "TOOL ok     %s%s %dms -> %d chars | %s",
            name,
            self._context(),
            elapsed_ms,
            len(text),
            _one_line(text, _OUTPUT_PREVIEW_CHARS),
        )
        self._fire(
            self._persist(
                tool_name=name,
                inputs=inputs,
                ok=True,
                duration_ms=elapsed_ms,
                output_chars=len(text),
                output_preview=text,
            )
        )

    async def on_tool_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        name, elapsed_ms, inputs = self._finish(run_id)
        logger.warning(
            "TOOL ERROR  %s%s %dms -> %s: %s",
            name,
            self._context(),
            elapsed_ms,
            type(error).__name__,
            error,
        )
        self._fire(
            self._persist(
                tool_name=name,
                inputs=inputs,
                ok=False,
                duration_ms=elapsed_ms,
                error_type=type(error).__name__,
                error_message=str(error),
            )
        )

    def _finish(self, run_id: UUID) -> tuple[str, int, Optional[dict]]:
        """Pop the start record; return (tool name, elapsed ms, start inputs)."""
        name, started_at, inputs = self._started.pop(
            run_id, ("tool", time.perf_counter(), None)
        )
        return name, int((time.perf_counter() - started_at) * 1000), inputs

    def _fire(self, coro: Coroutine[Any, Any, None]) -> None:
        """
        Run ``coro`` off the agent's critical path.

        Persistence must never add latency to a response, so the durable write
        is scheduled as a background task and the callback returns immediately --
        the agent proceeds to its next turn while the row is written
        concurrently. The task is parked in a module-level set (and removed on
        completion) so the loop keeps it alive until it finishes.
        """
        task = asyncio.create_task(coro)
        _PENDING.add(task)
        task.add_done_callback(_PENDING.discard)

    async def _persist(self, **fields: Any) -> None:
        """
        Write the durable row, in addition to the stdout line above.

        Runs in the background (see ``_fire``), off the agent's critical path.
        Imported lazily so this handler stays usable (and unit-testable) without
        a database, and so importing it never triggers engine construction. The
        service itself swallows write failures -- telemetry never breaks a run.
        """
        from .services import ToolCallLogService

        await ToolCallLogService.record(
            thread_id=self._thread_id, user_id=self._user_id, **fields
        )
