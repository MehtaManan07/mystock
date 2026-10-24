"""
Shared helpers for the tool layer.

Formatting and budget constants live here so every per-domain tool module reads
and renders numbers the same way. Nothing in here touches the database.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Union

# Products at or below this unit count are treated as "low stock" / needs
# reorder. A single flat threshold is deliberately crude -- the owner reasons in
# "handful left", not per-product reorder points, and a tool that needs a
# configured level per product would be unanswerable for most of the catalogue.
LOW_STOCK_THRESHOLD = 10

# Tool results are fed back to the model, so an unbounded list would blow the
# token budget on a single call. We cap rows and tell the model how many were
# hidden so it can say "showing 30 of 120" instead of silently lying.
MAX_ROWS = 30


def _inr(amount: Union[Decimal, float, int]) -> str:
    """
    Format a number the way the owner reads it: ``Rs 1,20,000``.

    Grouping is the Indian system (last three digits, then twos), not the
    western thousands grouping, because that is what every bill and ledger in
    this business uses and a mismatched number reads as wrong even when it is
    right.
    """
    n = int(Decimal(str(amount)).to_integral_value())
    sign = "-" if n < 0 else ""
    digits = str(abs(n))

    if len(digits) <= 3:
        grouped = digits
    else:
        last3 = digits[-3:]
        rest = digits[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3

    return f"Rs {sign}{grouped}"


def _period_start(days: Optional[int]) -> Optional[date]:
    """The earliest date to include for a 'last N days' window, or None for all time."""
    if days is None or days <= 0:
        return None
    return date.today() - timedelta(days=days)


def _truncation_note(total: int, shown: int) -> Optional[str]:
    """A '... and N more' line when a list was capped, else None."""
    if total > shown:
        return f"... and {total - shown} more (showing {shown} of {total})."
    return None
