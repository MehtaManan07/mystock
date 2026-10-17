"""
Assistant Runtime State

Threads, runs and pending actions, held in memory.

SINGLE-WORKER ASSUMPTION
------------------------
Everything here lives in the process that created it. `deployment/mystock.service`
starts uvicorn with no `--workers`, so there is exactly one process and this holds.

Adding `--workers` later would break the assistant in a confusing way: the POST
that starts a run could land on worker A while the SSE subscribe lands on worker
B, which has never heard of that run. The symptom would be a chat that hangs
forever with no error. If workers are ever added, this module has to move behind
Redis pub/sub *first*.

MEMORY
------
The box is an e2-micro and the unit file sets `MemoryMax=512M`, so everything
here is capped. The cap that matters is `MAX_EVENTS_PER_RUN`: an agent stuck in
a tool-calling loop is the most likely way to take the server down.

This is deliberately shaped like its replacement. Step 9 swaps the backing store
for Turso without changing a single caller.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from .events import BaseEvent, RunErrorEvent, RunFinishedEvent, is_terminal
from .widgets import Widget

logger = logging.getLogger(__name__)


MAX_EVENTS_PER_RUN = 2_000
MAX_MESSAGES_PER_THREAD = 500
MAX_THREADS_PER_USER = 200
MAX_COMPLETED_RUNS = 50
TITLE_MAX_CHARS = 60
DEFAULT_TITLE = "New chat"

RunStatus = Literal["running", "finished", "error", "cancelled"]
ActionStatus = Literal["pending", "confirmed", "cancelled"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def derive_title(text: str) -> str:
    """
    Title a thread from its first user message by truncation.

    Deliberately not an LLM call: a title is not worth a round trip, the tokens,
    or a second thing that can fail while the user is waiting for an answer.
    """
    cleaned = " ".join(text.split())
    if not cleaned:
        return DEFAULT_TITLE
    if len(cleaned) <= TITLE_MAX_CHARS:
        return cleaned
    cut = cleaned[:TITLE_MAX_CHARS]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,.;:-") + "\u2026"


# Records


@dataclass
class Message:
    id: str
    thread_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    widget: Optional[Widget] = None


@dataclass
class Thread:
    id: str
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    messages: List[Message] = field(default_factory=list)


@dataclass
class Run:
    id: str
    thread_id: str
    user_id: int
    created_at: datetime
    status: RunStatus = "running"
    events: List[BaseEvent] = field(default_factory=list)
    subscribers: List["asyncio.Queue"] = field(default_factory=list)
    task: Optional["asyncio.Task"] = None
    cancel_requested: bool = False
    seq: int = 0


@dataclass
class PendingAction:
    """A write the agent wants to make, staged until the user approves it."""

    id: str
    thread_id: str
    user_id: int
    kind: str
    payload: dict
    created_at: datetime
    status: ActionStatus = "pending"
    decided_at: Optional[datetime] = None


# Threads


class ThreadStore:
    """Conversations, scoped by user. Every read checks ownership."""

    def __init__(self) -> None:
        self._threads: Dict[str, Thread] = {}
        self._lock = asyncio.Lock()

    async def create(self, user_id: int, title: str = DEFAULT_TITLE) -> Thread:
        now = _now()
        thread = Thread(id=_new_id("thr"), user_id=user_id, title=title, created_at=now, updated_at=now)
        async with self._lock:
            self._threads[thread.id] = thread
            self._evict_threads_locked(user_id)
        return thread

    async def get(self, thread_id: str, user_id: int) -> Optional[Thread]:
        async with self._lock:
            return self._get_locked(thread_id, user_id)

    async def list(self, user_id: int) -> List[Thread]:
        async with self._lock:
            threads = [
                t for t in self._threads.values() if t.user_id == user_id and t.deleted_at is None
            ]
        return sorted(threads, key=lambda t: t.updated_at, reverse=True)

    async def rename(self, thread_id: str, user_id: int, title: str) -> Optional[Thread]:
        async with self._lock:
            thread = self._get_locked(thread_id, user_id)
            if thread is None:
                return None
            thread.title = title.strip()[:TITLE_MAX_CHARS] or DEFAULT_TITLE
            thread.updated_at = _now()
            return thread

    async def soft_delete(self, thread_id: str, user_id: int) -> bool:
        async with self._lock:
            thread = self._get_locked(thread_id, user_id)
            if thread is None:
                return False
            thread.deleted_at = _now()
            return True

    async def add_message(
        self,
        thread_id: str,
        user_id: int,
        role: Literal["user", "assistant"],
        content: str,
        widget: Optional[Widget] = None,
    ) -> Optional[Message]:
        async with self._lock:
            thread = self._get_locked(thread_id, user_id)
            if thread is None:
                return None

            is_first_user_message = role == "user" and not any(m.role == "user" for m in thread.messages)

            message = Message(
                id=_new_id("msg"),
                thread_id=thread_id,
                role=role,
                content=content,
                created_at=_now(),
                widget=widget,
            )
            thread.messages.append(message)
            if len(thread.messages) > MAX_MESSAGES_PER_THREAD:
                del thread.messages[: len(thread.messages) - MAX_MESSAGES_PER_THREAD]

            if is_first_user_message and thread.title == DEFAULT_TITLE:
                thread.title = derive_title(content)
            thread.updated_at = message.created_at
            return message

    def _get_locked(self, thread_id: str, user_id: int) -> Optional[Thread]:
        thread = self._threads.get(thread_id)
        if thread is None or thread.user_id != user_id or thread.deleted_at is not None:
            return None
        return thread

    def _evict_threads_locked(self, user_id: int) -> None:
        owned = sorted(
            (t for t in self._threads.values() if t.user_id == user_id),
            key=lambda t: t.updated_at,
        )
        for thread in owned[: max(0, len(owned) - MAX_THREADS_PER_USER)]:
            logger.warning("evicting thread %s to stay under the in-memory cap", thread.id)
            self._threads.pop(thread.id, None)


# Runs


class RunRegistry:
    """
    Owns in-flight agent runs: their event log, their subscribers and their task.
    """

    def __init__(self) -> None:
        self._runs: Dict[str, Run] = {}
        self._lock = asyncio.Lock()

    async def start(self, thread_id: str, user_id: int, agent: AsyncIterator[BaseEvent]) -> Run:
        """
        Start a run and return immediately. The caller gets a `run_id` to stream
        from; it does not wait for the agent.
        """
        run = Run(id=_new_id("run"), thread_id=thread_id, user_id=user_id, created_at=_now())
        async with self._lock:
            self._runs[run.id] = run
            self._evict_runs_locked()

        # The task is referenced by `run.task`, and `run` by `self._runs`. Without
        # a strong reference anywhere, asyncio is free to garbage-collect a
        # running task mid-flight.
        run.task = asyncio.create_task(self._drive(run, agent), name=f"assistant-run-{run.id}")
        run.task.add_done_callback(self._on_task_done)
        return run

    async def get(self, run_id: str, user_id: int) -> Optional[Run]:
        async with self._lock:
            run = self._runs.get(run_id)
            return run if run is not None and run.user_id == user_id else None

    async def active_run_for_thread(self, thread_id: str) -> Optional[Run]:
        """
        The run currently executing on a thread, if any.

        Two runs on one thread would interleave their events into the same
        conversation and race to append messages. The caller refuses to start a
        second one rather than trying to merge them.
        """
        async with self._lock:
            for run in self._runs.values():
                if run.thread_id == thread_id and run.status == "running":
                    return run
            return None

    async def subscribe(
        self, run_id: str, user_id: int, after_seq: int = 0
    ) -> Optional[Tuple[List[BaseEvent], "asyncio.Queue"]]:
        """
        Attach to a run. Returns the events already missed, plus a queue of
        everything from here on. `None` on the queue means the run is over.

        Taking the backlog snapshot and registering the queue happen under the
        same lock `_emit` holds. That is the entire point of this method. Done as
        two separate steps, an event emitted in between would land in neither the
        backlog nor the queue and be lost silently -- a bug that only appears
        when the agent happens to be fast, which is exactly when nobody is
        looking for it.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.user_id != user_id:
                return None

            backlog = [event for event in run.events if event.seq > after_seq]
            queue: "asyncio.Queue" = asyncio.Queue()
            if run.status == "running":
                run.subscribers.append(queue)
            else:
                # Already finished. Release the consumer rather than letting it
                # block forever on a queue nothing will ever write to.
                queue.put_nowait(None)
            return backlog, queue

    async def unsubscribe(self, run_id: str, queue: "asyncio.Queue") -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is not None and queue in run.subscribers:
                run.subscribers.remove(queue)

    async def cancel(self, run_id: str, user_id: int) -> bool:
        """
        Ask a run to stop at the next clean boundary.

        Cooperative on purpose. `task.cancel()` raises at whatever await point
        the agent happens to be sitting on, which can tear down a half-applied
        write and skips the terminal event the UI needs to stop spinning. The
        cost is latency: a run blocked in a slow upstream call will not notice
        until that call returns.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.user_id != user_id or run.status != "running":
                return False
            run.cancel_requested = True
            return True

    async def _drive(self, run: Run, agent: AsyncIterator[BaseEvent]) -> None:
        """Consume the agent and fan its events out. Always ends in a terminal event."""
        terminal_seen = False
        try:
            async for event in agent:
                if run.cancel_requested:
                    break
                if len(run.events) >= MAX_EVENTS_PER_RUN:
                    logger.error(
                        "run %s hit the %s event cap and was stopped", run.id, MAX_EVENTS_PER_RUN
                    )
                    await self._finish(
                        run,
                        RunErrorEvent(code="internal", message="The assistant got stuck and was stopped."),
                        "error",
                    )
                    return
                await self._emit(run, event)
                if is_terminal(event):
                    terminal_seen = True
                    break
        except asyncio.CancelledError:
            await self._finish(run, RunErrorEvent(code="cancelled", message="Cancelled."), "cancelled")
            raise
        except Exception:
            logger.exception("assistant run %s failed", run.id)
            await self._finish(
                run,
                RunErrorEvent(code="internal", message="Something went wrong. Please try again."),
                "error",
            )
            return
        finally:
            await _aclose(agent)

        if terminal_seen:
            status: RunStatus = "error" if run.events[-1].type == "run_error" else "finished"
            await self._finish(run, None, status)
        elif run.cancel_requested:
            await self._finish(run, RunErrorEvent(code="cancelled", message="Cancelled."), "cancelled")
        else:
            await self._finish(run, RunFinishedEvent(), "finished")

    async def _emit(self, run: Run, event: BaseEvent) -> None:
        """Stamp an event with its sequence number, log it and fan it out."""
        async with self._lock:
            if run.status != "running":
                return
            run.seq += 1
            stamped = event.model_copy(update={"seq": run.seq, "ts": _now()})
            run.events.append(stamped)
            for queue in run.subscribers:
                queue.put_nowait(stamped)

    async def _finish(self, run: Run, terminal: Optional[BaseEvent], status: RunStatus) -> None:
        """
        End a run exactly once, optionally emitting a final event.

        Bypasses the event cap: a run that hit the cap still has to deliver its
        terminal event, or every connected client spins forever.
        """
        async with self._lock:
            if run.status != "running":
                return
            if terminal is not None:
                run.seq += 1
                stamped = terminal.model_copy(update={"seq": run.seq, "ts": _now()})
                run.events.append(stamped)
                for queue in run.subscribers:
                    queue.put_nowait(stamped)
            run.status = status
            for queue in run.subscribers:
                queue.put_nowait(None)
            run.subscribers.clear()

    def _evict_runs_locked(self) -> None:
        completed = sorted(
            (r for r in self._runs.values() if r.status != "running"), key=lambda r: r.created_at
        )
        for run in completed[: max(0, len(completed) - MAX_COMPLETED_RUNS)]:
            self._runs.pop(run.id, None)

    @staticmethod
    def _on_task_done(task: "asyncio.Task") -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("assistant run task %s raised", task.get_name(), exc_info=exc)


async def _aclose(agent: AsyncIterator[BaseEvent]) -> None:
    """Let the agent run its own cleanup, whatever happened upstream."""
    aclose = getattr(agent, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:
        logger.exception("failed to close assistant agent generator")


# Pending actions


class ActionStore:
    """Writes staged by the agent, awaiting the user's decision."""

    def __init__(self) -> None:
        self._actions: Dict[str, PendingAction] = {}
        self._lock = asyncio.Lock()

    async def stage(self, thread_id: str, user_id: int, kind: str, payload: dict) -> PendingAction:
        action = PendingAction(
            id=_new_id("act"),
            thread_id=thread_id,
            user_id=user_id,
            kind=kind,
            payload=payload,
            created_at=_now(),
        )
        async with self._lock:
            self._actions[action.id] = action
        return action

    async def get(self, action_id: str, user_id: int) -> Optional[PendingAction]:
        async with self._lock:
            action = self._actions.get(action_id)
            return action if action is not None and action.user_id == user_id else None

    async def decide(
        self, action_id: str, user_id: int, decision: Literal["confirm", "cancel"]
    ) -> Tuple[Optional[PendingAction], bool]:
        """
        Record the user's decision. Returns `(action, transitioned)`.

        Idempotent: the first decision wins, and `transitioned` is False for
        every repeat. A double-tapped Confirm button or a retried request must
        not apply the same write twice, so the caller performs the write only
        when `transitioned` is True. `(None, False)` means unknown or not yours.
        """
        async with self._lock:
            action = self._actions.get(action_id)
            if action is None or action.user_id != user_id:
                return None, False
            if action.status != "pending":
                logger.info("action %s already %s; ignoring repeat decision", action.id, action.status)
                return action, False
            action.status = "confirmed" if decision == "confirm" else "cancelled"
            action.decided_at = _now()
            return action, True


# Single-worker process state. See the module docstring before adding --workers.
thread_store = ThreadStore()
run_registry = RunRegistry()
action_store = ActionStore()
