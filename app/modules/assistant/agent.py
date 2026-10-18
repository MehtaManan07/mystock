"""
The agent: a thread in, a stream of events out.

Context is assembled *only* from persisted messages. That is not a detail --
it is the mechanism that keeps the agent's own thinking out of its input.
Status lines and tool notices are never written to the database, so there is
no path by which they can reach this function, let alone the model. If
thoughts were ever persisted, the obvious "join everything in the thread"
prompt build would start replaying the agent's musings back at it, and on a
small free-tier token budget that gets expensive before it gets wrong.

The agent yields events and never touches the database to record its own
output. Persisting the reply belongs to ``runtime.py``, which does it inside
the same transaction that closes the run.
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator, List

from .events import (
    AgentEvent,
    RunStatusEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from .llm import ChatMessage, get_llm
from .models import MessageRole
from .services import MessageService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the assistant for a wholesale paper and packaging business. "
    "You answer questions about expenses, stock and sales using the "
    "business's own records. Be direct and use Indian number formatting "
    "(Rs 1,20,000). If you do not have the data to answer, say so plainly "
    "rather than guessing."
)

# A crude but honest budget. The free tier allows roughly 8k tokens a minute,
# and a runaway thread would spend it on history alone. Characters are used
# rather than tokens because this must not depend on a tokeniser that the
# stub does not have; it is deliberately conservative.
MAX_CONTEXT_CHARS = 12_000


def build_context(messages: List) -> List[ChatMessage]:
    """
    Most recent history that fits the budget, oldest first.

    Trimming from the front keeps the live part of the conversation and drops
    the archaeology, which is the right trade when something has to go.
    """
    context: List[ChatMessage] = []
    budget = MAX_CONTEXT_CHARS

    for message in reversed(messages):
        cost = len(message.content)
        if cost > budget:
            break
        budget -= cost
        context.append(
            ChatMessage(
                role=(
                    "user" if message.role == MessageRole.USER else "assistant"
                ),
                content=message.content,
            )
        )

    context.reverse()
    return [ChatMessage(role="system", content=SYSTEM_PROMPT)] + context


async def run_agent(thread_id: int, user_id: int) -> AsyncIterator[AgentEvent]:
    """
    Answer the latest message on a thread.

    Yields the agent's visible thinking and then its reply. Cancellation is
    handled by the caller, which stops consuming; because every fragment is a
    separate yield, that takes effect between tokens rather than at the end.
    """
    yield RunStatusEvent(status="thinking")

    history = await MessageService.list_for_thread(user_id, thread_id)
    context = build_context(history)

    llm = get_llm()
    # A per-stream correlation handle so the client can group the deltas it
    # receives into one bubble. It is not the persisted message's id -- that
    # row does not exist yet and is assigned by the database when the run
    # concludes.
    message_id = uuid.uuid4().hex

    yield RunStatusEvent(status="generating")
    yield TextMessageStartEvent(message_id=message_id)

    async for fragment in llm.stream(context):
        yield TextMessageContentEvent(message_id=message_id, delta=fragment)

    yield TextMessageEndEvent(message_id=message_id)
