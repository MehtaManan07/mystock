"""
The agent: a thread in, a stream of events out.

What happens between those two points is now a *graph* (see ``graph.py``), not a
straight line. The model can look things up, read what it found, and decide
again before it answers. This function's job is narrow and unchanged in shape:
assemble the input, drive the graph, and relay the events the runtime streams to
the browser.

Context is assembled *only* from persisted messages. That is not a detail --
it is the mechanism that keeps the agent's own thinking out of its input.
Status lines and tool notices are never written to the database, so there is no
path by which they can reach this function, let alone the model. Tool results
live in the graph's state and die with the run. If any of that were persisted,
the obvious "join everything in the thread" prompt build would start replaying
the agent's musings back at it, and on a small free-tier token budget that gets
expensive before it gets wrong.

The agent yields events and never touches the database to record its own
output. Persisting the reply belongs to ``runtime.py``, which does it inside the
same transaction that closes the run.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .adapter import stream_graph_events
from .events import AgentEvent
from .graph import get_graph
from .models import MessageRole
from .observability import ToolCallLogger
from .services import MessageService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the assistant for a wholesale paper and packaging business. "
    "You answer questions about stock, sales, purchases, contacts and expenses "
    "using the business's own records. You have read-only tools -- use them to "
    "ground every factual answer rather than guessing, and never invent numbers. "
    "Be direct and use Indian number formatting (Rs 1,20,000). If the tools do "
    "not give you what is needed to answer, say so plainly."
)

# A crude but honest budget. The free tier allows roughly 8k tokens a minute,
# and a runaway thread would spend it on history alone. Characters are used
# rather than tokens because this must not depend on a tokeniser; it is
# deliberately conservative.
MAX_CONTEXT_CHARS = 12_000


def build_context(messages: List) -> List[BaseMessage]:
    """
    Most recent history that fits the budget, oldest first, as graph input.

    Trimming from the front keeps the live part of the conversation and drops
    the archaeology, which is the right trade when something has to go. The
    system prompt is prepended last so it is always present regardless of how
    much history survived the trim.
    """
    context: List[BaseMessage] = []
    budget = MAX_CONTEXT_CHARS

    for message in reversed(messages):
        cost = len(message.content)
        if cost > budget:
            break
        budget -= cost
        if message.role == MessageRole.USER:
            context.append(HumanMessage(content=message.content))
        else:
            context.append(AIMessage(content=message.content))

    context.reverse()
    return [SystemMessage(content=SYSTEM_PROMPT)] + context


async def run_agent(thread_id: int, user_id: int) -> AsyncIterator[AgentEvent]:
    """
    Answer the latest message on a thread by driving the agent graph.

    Yields the agent's visible progress (status, tool chips) and its streamed
    reply. Cancellation is handled by the caller, which stops consuming; because
    every fragment is a separate yield, that takes effect between tokens rather
    than at the end.
    """
    history = await MessageService.list_for_thread(user_id, thread_id)
    messages = build_context(history)

    graph = get_graph()
    callbacks = [ToolCallLogger(thread_id=thread_id, user_id=user_id)]
    async for event in stream_graph_events(graph, messages, callbacks=callbacks):
        yield event
