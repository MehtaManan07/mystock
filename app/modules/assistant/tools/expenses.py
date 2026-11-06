"""Expense/income summary tool: recorded spends and earnings by category."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.modules.payments.service import PaymentsService

from app.modules.assistant.tools._shared import MAX_ROWS, _inr, _period_start
from app.modules.assistant.widgets import TableCell, TableColumn, TableWidget

LABELS = {"get_expense_summary": "Adding up expenses"}


@tool(response_format="content_and_artifact")
async def get_expense_summary(days: Optional[int] = 30) -> tuple[str, Optional[dict]]:
    """Summarise manually recorded spends and earnings, broken down by category.

    Covers standalone payments the owner logs directly (diesel, rent, misc
    income) -- not the income/expense implied by sales and purchases, which is in
    get_business_summary.

    Args:
        days: how far back to look (default 30). Use None for all time.

    Use for "what did we spend on this month", "expense breakdown", or recorded
    earnings by category.

    The category breakdown is shown to the user as a table; you receive only a
    one-line summary with the headline totals, so lead with those in a sentence
    and do not re-list the categories.
    """
    start = _period_start(days)
    summary = await PaymentsService.get_summary(from_date=start, to_date=None)

    window = f"last {days} days" if days else "all time"
    headline = (
        f"Spends {_inr(summary.total_spends)} \u00b7 "
        f"Earnings {_inr(summary.total_earnings)} \u00b7 "
        f"{summary.payment_count} entries"
    )

    # No category rows means there is no table to show -- fall back to a plain
    # one-line answer rather than an empty widget.
    if not summary.category_breakdown:
        return f"Expenses / income ({window}): {headline}.", None

    ordered = sorted(
        summary.category_breakdown.items(),
        key=lambda kv: Decimal(str(kv[1])),
        reverse=True,
    )
    shown = ordered[:MAX_ROWS]

    widget = TableWidget(
        title=f"Expenses / income ({window})",
        summary=headline,
        columns=[
            TableColumn(label="Category"),
            TableColumn(label="Amount", align="right"),
        ],
        rows=[
            [TableCell(text=category), TableCell(text=_inr(amount))]
            for category, amount in shown
        ],
        truncation_note=None,
    )

    content = (
        f"Displayed the expense/income breakdown ({window}): {headline}. "
        "Lead with those totals in one sentence; do not re-list the categories."
    )
    return content, widget.model_dump()
