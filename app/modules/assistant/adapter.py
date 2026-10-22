"""
The adapter: LangGraph's event stream in, our streaming contract out.

LangGraph and our runtime each own half of this system and neither should learn
the other's vocabulary. LangGraph speaks ``astream_events`` -- a firehose of
``on_chat_model_stream`` / ``on_tool_start`` / ``on_tool_end`` callbacks across
every runnable in the graph. Our frontend speaks ``AgentEvent`` -- a small,
deliberate set of lifecycle events (see ``events.py``). This module is the only
place that knows both, so the graph stays ignorant of SSE and the runtime stays
ignorant of LangGraph.

WHAT IT TRANSLATES
------------------
- model text deltas      → text_message_start / _content / _end
- a tool starting        → tool_call_start   (carrying the user-facing label)
- a tool finishing       → tool_call_end
- the gaps in between     → run_status (thinking / generating)

WHAT IT DELIBERATELY DROPS
--------------------------
Tool *arguments* and tool *results* never leave here. The UI is told a tool ran
and whether it succeeded, nothing more; the actual data stays in graph state
where the model reads it. That is the same ephemerality rule the contract
enforces, applied at the point the two worlds meet.

MESSAGE BOUNDARIES
------------------
One model turn that produces text becomes one text bubble. A turn that only
calls tools produces no bubble at all (empty content), so the tool-calling
round trips stay invisible and only the spoken answer is shown. Each bubble
gets a fresh ``message_id`` so the client can group its deltas; the deltas are
re-joined server-side into the persisted reply regardless of how many bubbles
there were.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, Optional

from langchain_core.runnables import Runnable

from .events import (
    AgentEvent,
    RunStatusEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from .tools import label_for


def _text_of(chunk: Any) -> str:
    """
    The plain-text delta carried by a model chunk.

    A chunk's ``content`` is usually a string, but some providers return a list
    of typed content blocks. Only the text is streamed to the user; tool-call
    chunks and any non-text blocks are ignored here (tools surface through the
    tool events instead).
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


async def stream_graph_events(
    graph: Runnable, messages: list
) -> AsyncIterator[AgentEvent]:
    """
    Run the graph and yield our events as the graph works.

    Emits status, tool and text events only. The run's envelope
    (``run_started`` / ``run_finished`` / errors) belongs to the runtime, which
    wraps this stream -- the adapter is concerned solely with what happens
    *during* the run.
    """
    current_message_id: Optional[str] = None
    generating = False

    yield RunStatusEvent(status="thinking")

    async for event in graph.astream_events({"messages": messages}, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            delta = _text_of(event["data"].get("chunk"))
            if not delta:
                continue

            if current_message_id is None:
                current_message_id = uuid.uuid4().hex
                if not generating:
                    generating = True
                    yield RunStatusEvent(status="generating")
                yield TextMessageStartEvent(message_id=current_message_id)

            yield TextMessageContentEvent(
                message_id=current_message_id, delta=delta
            )

        elif kind == "on_chat_model_end":
            # Close this bubble if the turn spoke. A tool-only turn opened no
            # bubble, so there is nothing to end.
            if current_message_id is not None:
                yield TextMessageEndEvent(message_id=current_message_id)
                current_message_id = None

        elif kind == "on_tool_start":
            tool_name = event.get("name", "")
            yield ToolCallStartEvent(
                tool_call_id=event["run_id"],
                tool_name=tool_name,
                label=label_for(tool_name),
            )
            # After a tool runs the model will think again before it answers.
            generating = False
            yield RunStatusEvent(status="thinking")

        elif kind == "on_tool_end":
            yield ToolCallEndEvent(tool_call_id=event["run_id"], ok=True)
