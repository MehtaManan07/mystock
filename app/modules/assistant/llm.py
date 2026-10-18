"""
The model call. **This is the only stubbed file in the assistant.**

Everything around it -- persistence, streaming, cancellation, the API -- is
real. Swapping the stub for Groq means writing one class here and changing
``get_llm()``. No other module imports an implementation, only the protocol,
so nothing else moves.

WHY THE INTERFACE IS TOKENS, NOT A STRING
-----------------------------------------
Returning a finished string would make the stub trivially simpler and would
quietly delete the hardest property of the system: that an answer arrives
incrementally, can be watched from two tabs, and can be cancelled halfway. A
token stream is the real shape of the problem, so the fake has that shape too.
"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from typing import AsyncIterator, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    """One turn of context sent to the model."""

    role: str  # "system" | "user" | "assistant"
    content: str


@runtime_checkable
class LLM(Protocol):
    """
    A streaming chat model.

    Implementations must yield text fragments as they arrive and must be
    cancellable between fragments -- a caller that stops consuming has to be
    able to stop the model.
    """

    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        ...


class StubLLM:
    """
    A stand-in that streams plausible text at a human-ish rate.

    It does not understand anything. It picks a reply by keyword so the
    surface can be exercised end to end -- streaming, reconnects, cancels,
    persistence -- without burning tokens or needing prompts to be right yet.
    """

    # Seconds between fragments. Slow enough that cancelling mid-answer is
    # something you can actually do by hand while testing.
    MIN_DELAY = 0.02
    MAX_DELAY = 0.06

    _REPLIES = (
        (
            ("transport", "freight", "cartage", "delivery"),
            "Transport came to **Rs 12,400** this month across 9 entries. "
            "That is up about 18% on last month, mostly from three larger "
            "lorry bookings in the second week.",
        ),
        (
            ("expense", "spend", "spent", "cost"),
            "You have recorded **Rs 48,920** of expenses this month. The "
            "largest categories are transport, packing material and rent. "
            "Nothing looks out of line with last month apart from transport.",
        ),
        (
            ("stock", "inventory", "quantity", "qty"),
            "Stock is holding steady. Two items are below their reorder "
            "level: Meena Mor 1x2 and the 40x60 kraft sheets. Everything "
            "else has at least three weeks of cover.",
        ),
        (
            ("bill", "invoice", "gst"),
            "I can read bills and answer questions about them, but I am not "
            "wired up to issue invoices yet. That lands in a later phase, "
            "once the expense and inventory flows are solid.",
        ),
    )

    _FALLBACK = (
        "I can help with expenses, stock levels and what the numbers have "
        "been doing lately. Ask me something like *how much did I spend on "
        "transport this month* and I will pull it up."
    )

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        prompt = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        ).lower()

        text = self._FALLBACK
        for keywords, reply in self._REPLIES:
            if any(word in prompt for word in keywords):
                text = reply
                break

        # Split so whitespace is preserved exactly; joining the fragments
        # must reproduce the source text byte for byte, because that is what
        # gets persisted.
        for fragment in re.findall(r"\S+\s*", text):
            await asyncio.sleep(random.uniform(self.MIN_DELAY, self.MAX_DELAY))
            yield fragment


def get_llm() -> LLM:
    """
    The single swap point.

    Replacing this return value with a Groq-backed client is the entire
    change needed to go live.
    """
    return StubLLM()
