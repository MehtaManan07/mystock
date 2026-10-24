"""Expense/income summary tool: recorded spends and earnings by category."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.modules.payments.service import PaymentsService

from ._shared import MAX_ROWS, _inr, _period_start

LABELS = {"get_expense_summary": "Adding up expenses"}


@tool
async def get_expense_summary(days: Optional[int] = 30) -> str:
    """Summarise manually recorded spends and earnings, broken down by category.

    Covers standalone payments the owner logs directly (diesel, rent, misc
    income) -- not the income/expense implied by sales and purchases, which is in
    get_business_summary.

    Args:
        days: how far back to look (default 30). Use None for all time.

    Use for "what did we spend on this month", "expense breakdown", or recorded
    earnings by category.
    """
    start = _period_start(days)
    summary = await PaymentsService.get_summary(from_date=start, to_date=None)

    window = f"last {days} days" if days else "all time"
    lines = [
        f"EXPENSE / INCOME SUMMARY ({window})",
        f"- Total spends: {_inr(summary.total_spends)}",
        f"- Total earnings: {_inr(summary.total_earnings)}",
        f"- Entries: {summary.payment_count}",
    ]

    if summary.category_breakdown:
        lines.append("")
        lines.append("BY CATEGORY")
        ordered = sorted(
            summary.category_breakdown.items(),
            key=lambda kv: Decimal(str(kv[1])),
            reverse=True,
        )
        for category, amount in ordered[:MAX_ROWS]:
            lines.append(f"- {category}: {_inr(amount)}")

    return "\n".join(lines)
