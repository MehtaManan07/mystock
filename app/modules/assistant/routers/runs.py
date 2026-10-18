"""
Runs: fetch a run, cancel it, and watch it over SSE.

Most of the API is ordinary CRUD. The exception is the stream, which has three
sharp edges worth stating out loud.

1. **The response interceptor buffers whole bodies.** It reads
   ``response.body_iterator`` to completion before replying, which for an
   endless stream means it never replies at all. It bails out on non-JSON
   content types, so ``text/event-stream`` escapes -- but the stream route is
   also marked ``@skip_interceptor`` so that this does not depend on a
   content-type check in unrelated middleware continuing to behave.

2. **nginx buffers proxied responses by default.** Without
   ``proxy_buffering off`` -- or the ``X-Accel-Buffering: no`` header sent
   below -- the whole answer arrives at once when the run ends. This works
   perfectly in local development and fails only in production, which is the
   worst possible failure mode.

3. **Reconnects must not replay the agent's thinking.** Resume is by
   ``Last-Event-ID``; the registry replays durable events only, so a client
   that drops and returns sees the same transcript as one that never left.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, get_current_user

from ..events import format_heartbeat, format_sse
from ..runtime import run_registry
from ..schemas import RunResponse
from ..services import RunService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["assistant"])

# Long enough not to be chatty, short enough to keep intermediaries from
# deciding an idle connection is dead.
HEARTBEAT_SECONDS = 15.0


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    return await RunService.get(current_user.user_id, run_id)


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Stop a run, keeping whatever it has already said.

    Cancelling something that already finished is not an error; the client
    may well have clicked as the last token arrived.
    """
    cancelled = await run_registry.cancel(run_id, current_user.user_id)
    return {"cancelled": cancelled}


@router.get("/{run_id}/stream")
@skip_interceptor
async def stream_run(
    request: Request,
    run_id: int,
    after_seq: int = Query(0, ge=0, description="Resume after this event"),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Watch a run.

    Any number of clients may watch the same run; each gets every event from
    its resume point onwards. ``Last-Event-ID`` takes precedence over the
    query parameter, because the browser sets it automatically on reconnect.
    """
    resume_from = after_seq
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        try:
            resume_from = max(resume_from, int(last_event_id))
        except ValueError:
            logger.warning("Ignoring malformed Last-Event-ID: %r", last_event_id)

    # Raises before the response starts, so a bad run id is a clean 404
    # rather than an error delivered inside a stream the client has already
    # begun reading.
    backlog, queue = await run_registry.subscribe(
        run_id, current_user.user_id, resume_from
    )

    async def events() -> AsyncIterator[str]:
        try:
            for event in backlog:
                yield format_sse(event)

            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    # Also the cheapest way to notice the client vanished:
                    # writing to a dead connection raises here.
                    yield format_heartbeat()
                    continue

                if event is None:
                    break
                yield format_sse(event)
        finally:
            # Runs when the client disconnects as well as on a clean finish.
            # Without it, queues accumulate for the life of the process.
            await run_registry.unsubscribe(run_id, queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Tells nginx not to buffer this response. Without it the stream
            # arrives in one lump in production and nowhere else.
            "X-Accel-Buffering": "no",
        },
    )
