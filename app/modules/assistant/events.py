"""
Assistant Streaming Contract

The events the server streams to the UI over SSE for a single agent run.

Event names follow the subset of the AG-UI protocol we actually need
(https://docs.ag-ui.com/concepts/events), so that adopting AG-UI properly later
is a rename rather than a rewrite. We are not using their SDKs: one owned
backend talking to one owned frontend does not need an interop protocol.

We stream lifecycle, not tokens. The latency a user feels here is tool
execution and rate-limit waits, not generation, so the events that matter are
"what is it doing" rather than "here is the next character". `text_message_*`
still carries deltas so that real token streaming can be switched on later
without a client change; the dummy agent simply emits one content event holding
the whole message.

Transport notes:
  - Frames are `id: <seq>`, `data: <json>`, blank line.
  - There is no SSE `event:` name. The discriminator lives in the JSON `type`
    field so the client has exactly one parse path.
  - nginx defaults to `proxy_buffering on`, which holds the entire stream and
    delivers it in one go. It must be turned off for this route, and the
    response must carry `X-Accel-Buffering: no`. This works locally either way,
    because local dev talks to uvicorn directly.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from .widgets import Widget


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BaseEvent(BaseModel):
    """
    Envelope fields present on every streamed event.

    Agents construct events *without* a `seq`: sequence numbering belongs to the
    run, not to the thing producing events. `RunRegistry` stamps the real value
    on emit, and `format_sse` refuses to put an unstamped event on the wire.
    """

    seq: int = Field(
        0, ge=0, description="Monotonic sequence within the run, from 1. 0 means not yet stamped"
    )
    ts: datetime = Field(default_factory=_now, description="Server emit time, UTC")


# Lifecycle


class RunStartedEvent(BaseEvent):
    """Always the first event of a run."""

    type: Literal["run_started"] = "run_started"
    run_id: str
    thread_id: str


class RunStatusEvent(BaseEvent):
    """
    Human-readable progress for the gaps between tool calls.

    `throttled` matters more than it looks: on a free-tier token budget the
    agent will sometimes sit waiting on a rate limit, and without this event the
    UI just hangs silently with no explanation.
    """

    type: Literal["run_status"] = "run_status"
    status: Literal["thinking", "generating", "throttled"]
    message: Optional[str] = Field(None, max_length=200, description="Shown verbatim to the user")
    retry_in_seconds: Optional[int] = Field(None, ge=0, description="Set when status is 'throttled'")


class RunFinishedEvent(BaseEvent):
    """Terminal. The run completed; the stream closes after this."""

    type: Literal["run_finished"] = "run_finished"


class RunErrorEvent(BaseEvent):
    """Terminal. The run failed; the stream closes after this."""

    type: Literal["run_error"] = "run_error"
    code: Literal["rate_limited", "upstream_error", "cancelled", "internal"]
    message: str = Field(..., max_length=500, description="Safe to show the user; never raw exception text")


# Tool calls


class ToolCallStartEvent(BaseEvent):
    """A tool began executing. `label` is what the user sees, not the tool name."""

    type: Literal["tool_call_start"] = "tool_call_start"
    tool_call_id: str
    tool_name: str
    label: str = Field(..., max_length=120, description="e.g. 'Looking up October expenses'")


class ToolCallEndEvent(BaseEvent):
    """A tool finished. Results are model-internal and are not sent to the client."""

    type: Literal["tool_call_end"] = "tool_call_end"
    tool_call_id: str
    ok: bool = True


# Assistant message


class TextMessageStartEvent(BaseEvent):
    type: Literal["text_message_start"] = "text_message_start"
    message_id: str


class TextMessageContentEvent(BaseEvent):
    """Append `delta` to the buffer for `message_id`. The payload is markdown."""

    type: Literal["text_message_content"] = "text_message_content"
    message_id: str
    delta: str


class TextMessageEndEvent(BaseEvent):
    type: Literal["text_message_end"] = "text_message_end"
    message_id: str


# Widgets


class WidgetEvent(BaseEvent):
    """Maps to AG-UI's CUSTOM event. Named for readability over a zero-diff migration."""

    type: Literal["widget"] = "widget"
    widget: Widget


AgentEvent = Annotated[
    Union[
        RunStartedEvent,
        RunStatusEvent,
        ToolCallStartEvent,
        ToolCallEndEvent,
        TextMessageStartEvent,
        TextMessageContentEvent,
        TextMessageEndEvent,
        WidgetEvent,
        RunFinishedEvent,
        RunErrorEvent,
    ],
    Field(discriminator="type"),
]


TERMINAL_EVENT_TYPES = frozenset({"run_finished", "run_error"})


def is_terminal(event: BaseEvent) -> bool:
    """True when no further events will follow and the stream should close."""
    return getattr(event, "type", None) in TERMINAL_EVENT_TYPES


def format_sse(event: BaseEvent) -> str:
    """Render one event as an SSE frame. Rejects events the registry never stamped."""
    if event.seq < 1:
        raise ValueError(
            f"refusing to send an unstamped {getattr(event, 'type', '?')} event; "
            "seq is assigned by RunRegistry on emit"
        )
    payload = event.model_dump_json(exclude_none=True)
    return f"id: {event.seq}\ndata: {payload}\n\n"


def format_heartbeat() -> str:
    """
    An SSE comment frame. Carries no data and is ignored by the client parser.

    Sent periodically so that an idle run still produces bytes, which keeps
    proxies and mobile networks from dropping the connection mid-run.
    """
    return ": keepalive\n\n"
