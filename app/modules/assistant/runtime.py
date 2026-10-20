"""
The live half of a run.

``service.py`` owns what a run *was*; this owns what it *is doing*. A live run
is an ``asyncio.Task`` plus a fan-out of queues feeding every browser tab
currently watching, and none of that can be a database row -- which is exactly
why a process restart has to reconcile runs left marked ``running``.

ORDER OF OPERATIONS AT THE END OF A RUN
---------------------------------------
The reply is written to the database *before* the terminal event is emitted.
A client that sees ``run_finished`` may reload immediately, and if the write
were still in flight the answer it just watched appear would be missing. The
window is milliseconds wide on a local database, which is precisely why it
survives testing and fails in production.

CANCELLATION IS COOPERATIVE
---------------------------
Cancelling sets a flag; it does not call ``Task.cancel()``. A hard cancel can
land anywhere, including midway through the database write above, which would
produce the vanishing-answer bug on purpose. The loop checks the flag between
events instead, so cancellation always happens at a safe point.

SINGLE WORKER
-------------
The registry is process-local. Two workers mean a browser can ask worker B to
stream a run that only worker A knows about. Scaling out needs a shared bus
(Redis pub/sub or Postgres LISTEN/NOTIFY) and this module is the only thing
that would change.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Dict, List, Optional, Set, Tuple

from app.core.exceptions import NotFoundError

from .events import (
    AgentEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    is_ephemeral,
)
from .models import RunStatus
from .services import GENERIC_ERROR_TEXT, MessageService, RunService, ThreadService

logger = logging.getLogger(__name__)

# A reconnecting client replays the backlog. Cap it so a long run cannot grow
# without bound; the terminal event is always delivered regardless.
MAX_BACKLOG_EVENTS = 2000

# Finished runs linger briefly so a client that reconnects just after the end
# still receives the tail and the terminal event.
MAX_RETAINED_RUNS = 50

AgentFactory = Callable[[int, int], AsyncIterator[AgentEvent]]


@dataclass
class _Reply:
    """
    The assistant's answer, accumulated server-side.

    Deliberately built from what the agent *produced*, not from what any
    client received. The entire point is that it survives nobody watching.
    """

    parts: List[str] = field(default_factory=list)
    widget: Optional[dict] = None

    def observe(self, event: AgentEvent) -> None:
        # `AgentEvent` is a discriminated union, so comparing `type` narrows
        # to the member that actually carries `delta` / `widget`.
        if event.type == "text_message_content":
            self.parts.append(event.delta)
        elif event.type == "widget":
            self.widget = event.widget.model_dump()

    @property
    def text(self) -> str:
        return "".join(self.parts)


@dataclass
class LiveRun:
    id: int
    thread_id: int
    user_id: int

    seq: int = 0
    events: List[AgentEvent] = field(default_factory=list)
    subscribers: Set["asyncio.Queue"] = field(default_factory=set)

    # The *current* ephemeral state, retained so a client that attaches
    # mid-run is told what the agent is doing right now. This is a snapshot,
    # not a history: only the latest status is kept, and it is still never
    # persisted. The agent emits "thinking" and starts a slow context read
    # *before* the browser -- which only subscribes after the send POST
    # returns -- has opened the stream, so without this the very first
    # subscriber would miss every status line the run already produced.
    current_status: Optional[AgentEvent] = None
    # tool_call_id -> (start_event, end_event or None), in call order.
    live_tool_calls: "OrderedDict[str, Tuple[AgentEvent, Optional[AgentEvent]]]" = (
        field(default_factory=OrderedDict)
    )

    cancelled: bool = False
    finished: bool = False

    # Strong reference. Without it the task is only reachable from asyncio's
    # weak set and can be garbage collected mid-run.
    task: Optional["asyncio.Task"] = None


class RunRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._runs: "OrderedDict[int, LiveRun]" = OrderedDict()

    async def attach(
        self, record, agent_factory: AgentFactory
    ) -> LiveRun:
        """
        Begin streaming a run whose row already exists.

        The row is always created first, by ``start_turn`` below: its partial
        unique index is what actually enforces one live run per thread, and
        it must reject a second request *before* anything is written or any
        task is spawned.
        """
        live = LiveRun(
            id=record.id, thread_id=record.thread_id, user_id=record.user_id
        )
        async with self._lock:
            self._runs[live.id] = live
            self._evict_locked()

        agent = agent_factory(record.thread_id, record.user_id)
        live.task = asyncio.create_task(self._drive(live, agent))
        live.task.add_done_callback(self._log_task_result)
        return live

    async def get(self, run_id: int, user_id: int) -> Optional[LiveRun]:
        async with self._lock:
            live = self._runs.get(run_id)
            # Not found and not yours are the same answer.
            return live if live and live.user_id == user_id else None

    async def subscribe(
        self, run_id: int, user_id: int, after_seq: int = 0
    ) -> Tuple[List[AgentEvent], "asyncio.Queue"]:
        """
        Attach to a run, returning everything missed plus a live feed.

        Backlog and registration happen under one lock. Taking a snapshot and
        then subscribing would drop any event emitted in between, and the
        reverse order would deliver it twice.

        The backlog carries durable events plus the current ephemeral snapshot
        (the live status line and any in-flight tool chips), so a client that
        attaches mid-run sees what the agent is doing, not a blank pane. The
        snapshot is still filtered by ``after_seq``: a reconnecting client that
        already saw a status past its resume point does not get it again, and a
        finished run offers no snapshot at all.
        """
        async with self._lock:
            live = self._runs.get(run_id)
            if live is None or live.user_id != user_id:
                raise NotFoundError("Run", run_id)

            backlog = [e for e in live.events if e.seq > after_seq]
            if not live.finished:
                backlog = self._merge_snapshot(live, backlog, after_seq)
            queue: "asyncio.Queue" = asyncio.Queue()

            if live.finished:
                # Nothing further is coming. Release the consumer immediately
                # rather than leaving it waiting on a dead run.
                queue.put_nowait(None)
            else:
                live.subscribers.add(queue)

            return backlog, queue

    async def unsubscribe(self, run_id: int, queue: "asyncio.Queue") -> None:
        async with self._lock:
            live = self._runs.get(run_id)
            if live is not None:
                live.subscribers.discard(queue)

    async def cancel(self, run_id: int, user_id: int) -> bool:
        async with self._lock:
            live = self._runs.get(run_id)
            if live is None or live.user_id != user_id or live.finished:
                return False
            live.cancelled = True
            return True

    # -- driving ----------------------------------------------------------

    async def _drive(self, live: LiveRun, agent: AsyncIterator[AgentEvent]) -> None:
        """
        Pump the agent into every subscriber, then conclude exactly once.

        Every path through this function reaches exactly one ``_conclude``.
        """
        reply = _Reply()

        await self._emit(live, RunStartedEvent(run_id=live.id, thread_id=live.thread_id))

        try:
            async for event in agent:
                if live.cancelled:
                    break
                reply.observe(event)
                await self._emit(live, event)

            if live.cancelled:
                await self._conclude(live, RunStatus.CANCELLED, reply)
            else:
                await self._conclude(live, RunStatus.COMPLETED, reply)

        except asyncio.CancelledError:
            # Shutdown. Save what we have; do not swallow the cancellation.
            await self._conclude(live, RunStatus.CANCELLED, reply)
            raise
        except Exception:
            logger.exception("Run %s failed", live.id)
            await self._conclude(live, RunStatus.FAILED, reply)
        finally:
            await _aclose(agent)

    async def _conclude(self, live: LiveRun, status: str, reply: _Reply) -> None:
        """Persist, *then* announce. Never the other way round."""
        try:
            if status == RunStatus.COMPLETED:
                await RunService.complete(live.id, reply.text, reply.widget)
            elif status == RunStatus.CANCELLED:
                await RunService.cancel(live.id, reply.text)
            else:
                await RunService.fail(
                    live.id, "internal", GENERIC_ERROR_TEXT, reply.text
                )
        except Exception:
            # The reply is lost, but leaving subscribers hanging forever is
            # worse. Announce the end regardless.
            logger.exception("Could not persist the result of run %s", live.id)

        if status == RunStatus.FAILED:
            terminal: AgentEvent = RunErrorEvent(
                code="internal", message=GENERIC_ERROR_TEXT
            )
        else:
            terminal = RunFinishedEvent()

        await self._emit(live, terminal, final=True)

    async def _emit(
        self, live: LiveRun, event: AgentEvent, final: bool = False
    ) -> None:
        async with self._lock:
            live.seq += 1
            event.seq = live.seq

            # Durable events are replayed to any client that attaches or
            # reconnects. Ephemeral ones are not kept as history -- that would
            # let a reload change the transcript -- but the *latest* ephemeral
            # state is snapshotted so a new subscriber learns what the agent is
            # doing right now. The two are never confused: snapshot never
            # reaches the database, and the transcript never carries a status.
            if is_ephemeral(event):
                self._snapshot_ephemeral(live, event)
            else:
                live.events.append(event)
                if len(live.events) > MAX_BACKLOG_EVENTS:
                    del live.events[0]

            subscribers = list(live.subscribers)
            if final:
                live.finished = True
                live.subscribers.clear()
                # The run is over; its live status is meaningless now, and the
                # UI drops ephemerals on a terminal event anyway.
                live.current_status = None
                live.live_tool_calls.clear()

        for queue in subscribers:
            queue.put_nowait(event)
        if final:
            # The sentinel every consumer waits for.
            for queue in subscribers:
                queue.put_nowait(None)

    @staticmethod
    def _snapshot_ephemeral(live: LiveRun, event: AgentEvent) -> None:
        """
        Fold an ephemeral event into the run's live snapshot.

        Only the newest status survives, and tool calls collapse to their
        latest state per id (a start, then that start plus its end). Replaying
        this to a late subscriber reproduces the current ephemeral UI without
        replaying the whole run of thinking.
        """
        if event.type == "run_status":
            live.current_status = event
        elif event.type == "tool_call_start":
            live.live_tool_calls[event.tool_call_id] = (event, None)
        elif event.type == "tool_call_end":
            existing = live.live_tool_calls.get(event.tool_call_id)
            if existing is not None:
                live.live_tool_calls[event.tool_call_id] = (existing[0], event)

    @staticmethod
    def _merge_snapshot(
        live: LiveRun, backlog: List[AgentEvent], after_seq: int
    ) -> List[AgentEvent]:
        """
        Interleave the ephemeral snapshot into the durable backlog by ``seq``.

        Each snapshot event keeps its original sequence number, so a
        reconnecting client past that point is filtered out just like a durable
        event would be, and the merged stream stays in emission order.
        """
        snapshot: List[AgentEvent] = []
        if live.current_status is not None and live.current_status.seq > after_seq:
            snapshot.append(live.current_status)
        for start, end in live.live_tool_calls.values():
            if start.seq > after_seq:
                snapshot.append(start)
            if end is not None and end.seq > after_seq:
                snapshot.append(end)

        if not snapshot:
            return backlog
        return sorted([*backlog, *snapshot], key=lambda e: e.seq)

    def _evict_locked(self) -> None:
        if len(self._runs) <= MAX_RETAINED_RUNS:
            return
        for run_id, live in list(self._runs.items()):
            if len(self._runs) <= MAX_RETAINED_RUNS:
                break
            if live.finished:
                del self._runs[run_id]

    @staticmethod
    def _log_task_result(task: "asyncio.Task") -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("Run task crashed", exc_info=exc)


async def _aclose(agent: AsyncIterator[AgentEvent]) -> None:
    """Let the agent run its own cleanup, whatever happened upstream."""
    close = getattr(agent, "aclose", None)
    if close is None:
        return
    try:
        await close()
    except Exception:
        logger.exception("Agent cleanup failed")


run_registry = RunRegistry()


async def start_turn(
    user_id: int,
    thread_id: Optional[int],
    content: str,
    agent_factory: Optional[AgentFactory] = None,
):
    """
    Take one turn: claim the thread, record what was said, start answering.

    A ``thread_id`` of ``None`` opens a fresh conversation. The thread is
    created here rather than in the router so that the whole turn -- new
    thread, user message, run -- is decided in one place; the caller reads
    the resolved id back off the returned ``LiveRun``.

    The rest of the order is deliberate and is the reason this lives in one
    function rather than in the router.

    The run row is opened *first*, because that is the only thing that can
    atomically claim the thread. Appending the user's message first would
    mean that a second, concurrent send gets rejected only after its message
    is already stored -- leaving a question in the transcript that nothing
    will ever answer.

    If recording the message then fails, the run is closed rather than left
    holding the thread open forever.
    """
    from .agent import run_agent

    if thread_id is None:
        thread = await ThreadService.create(user_id)
        thread_id = thread.id

    record = await RunService.open(user_id, thread_id)

    try:
        message = await MessageService.append_user_message(
            user_id, thread_id, content
        )
    except Exception:
        await RunService.fail(record.id, "internal", GENERIC_ERROR_TEXT)
        raise

    live = await run_registry.attach(record, agent_factory or run_agent)
    return live, message
