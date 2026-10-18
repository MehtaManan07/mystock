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

WHAT SURVIVES THE RUN
---------------------
Events fall into three classes and are treated differently once the run ends.
See `EVENT_CLASSES` below for the two rules that matter -- in particular,
ephemeral events must never be fed back to the model as context.

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
from types import MappingProxyType
from typing import Annotated, Literal, Mapping, Optional, Union, get_args

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
        default=0, ge=0, description="Monotonic sequence within the run, from 1. 0 means not yet stamped"
    )
    ts: datetime = Field(default_factory=_now, description="Server emit time, UTC")


# Lifecycle


class RunStartedEvent(BaseEvent):
    """Always the first event of a run."""

    type: Literal["run_started"] = "run_started"
    run_id: int
    thread_id: int


class RunStatusEvent(BaseEvent):
    """
    Human-readable progress for the gaps between tool calls.

    `throttled` matters more than it looks: on a free-tier token budget the
    agent will sometimes sit waiting on a rate limit, and without this event the
    UI just hangs silently with no explanation.
    """

    type: Literal["run_status"] = "run_status"
    status: Literal["thinking", "generating", "throttled"]
    message: Optional[str] = Field(default=None, max_length=200, description="Shown verbatim to the user")
    retry_in_seconds: Optional[int] = Field(default=None, ge=0, description="Set when status is 'throttled'")


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


# What survives the run
#
# EPHEMERAL -- the agent's visible thinking. Two rules, both easy to get wrong:
#
#   1. The UI discards these when the run ends. A conversation then reads the
#      same whether you watched it happen or opened it an hour later. Keeping
#      them would make a page reload silently change the transcript, which
#      reads as a bug.
#   2. They must NEVER be fed back to the model as context. On an 8K TPM budget,
#      replaying "thinking..." and tool chatter is paying tokens to confuse the
#      model about what it already said. The natural way to build a prompt is to
#      join everything the run produced, so this has to be a deliberate filter.
#
# TRANSCRIPT -- the assistant's actual reply. Accumulated during the run and
# written to the thread as a `Message`, so it survives reload and restart.
#
# CONTROL -- stream bookkeeping. Meaningful while connected, meaningless after.
#
# One mapping rather than three sets, so a type cannot land in two classes at
# once -- `widget` marked both ephemeral and transcript would persist the reply
# *and* wipe it from the UI. A dict makes that unrepresentable instead of merely
# undetected. MappingProxyType for the same reason the sets are frozen: this is
# imported elsewhere and must not be mutable.
EventClass = Literal["ephemeral", "transcript", "control"]

EVENT_CLASSES: Mapping[str, EventClass] = MappingProxyType(
    {
        "run_status": "ephemeral",
        "tool_call_start": "ephemeral",
        "tool_call_end": "ephemeral",
        "text_message_start": "transcript",
        "text_message_content": "transcript",
        "text_message_end": "transcript",
        "widget": "transcript",
        "run_started": "control",
        "run_finished": "control",
        "run_error": "control",
    }
)


def _types_in(event_class: EventClass) -> frozenset:
    return frozenset(t for t, c in EVENT_CLASSES.items() if c == event_class)


EPHEMERAL_EVENT_TYPES = _types_in("ephemeral")
TRANSCRIPT_EVENT_TYPES = _types_in("transcript")
CONTROL_EVENT_TYPES = _types_in("control")

# A separate axis: both terminal events are also CONTROL, but "is this the last
# one" is a different question from "does this survive the run".
TERMINAL_EVENT_TYPES = frozenset({"run_finished", "run_error"})


def _declared_event_types() -> frozenset:
    """Every `type` literal in the union, read back off the models themselves."""
    members = get_args(get_args(AgentEvent)[0])
    return frozenset(m.model_fields["type"].default for m in members)


# An event nobody classified would default to invisible in the UI and, worse,
# might be silently replayed into the model. A leftover entry for a deleted
# event is the quieter version of the same mistake. Import time is the cheapest
# place to catch both.
_DECLARED = _declared_event_types()
_UNCLASSIFIED = _DECLARED - set(EVENT_CLASSES)
_STALE = set(EVENT_CLASSES) - _DECLARED
if _UNCLASSIFIED or _STALE:
    raise RuntimeError(
        f"EVENT_CLASSES is out of sync with AgentEvent: "
        f"unclassified={sorted(_UNCLASSIFIED)}, stale={sorted(_STALE)}"
    )


def is_terminal(event: AgentEvent) -> bool:
    """True when no further events will follow and the stream should close."""
    return event.type in TERMINAL_EVENT_TYPES


def is_ephemeral(event: AgentEvent) -> bool:
    """True for thinking/tool chatter: drop on run end, never send to the model."""
    return EVENT_CLASSES[event.type] == "ephemeral"


def format_sse(event: AgentEvent) -> str:
    """Render one event as an SSE frame. Rejects events the registry never stamped."""
    if event.seq < 1:
        raise ValueError(
            f"refusing to send an unstamped {event.type} event; "
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
