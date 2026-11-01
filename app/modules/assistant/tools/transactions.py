"""Transaction listing tool: recent sales and purchases."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.modules.transactions.models import PaymentStatus, TransactionType
from app.modules.transactions.schemas import TransactionFilterDto
from app.modules.transactions.service import TransactionsService

from app.modules.assistant.tools._shared import MAX_ROWS, _inr, _period_start, _truncation_note
from app.modules.assistant.tools.contacts import resolve_contact

LABELS = {"get_transactions": "Checking recent transactions"}


@tool
async def get_transactions(
    days: Optional[int] = 30,
    contact_name: Optional[str] = None,
    kind: Optional[str] = None,
    payment_status: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> str:
    """List recent sales and purchases, optionally filtered.

    Args:
        days: rolling window, how far back to look (default 30). Use None for
            all time. Ignored when from_date/to_date is given.
        contact_name: restrict to one customer/supplier by name. If the name
            matches more than one contact, this returns the choices instead of
            transactions so you can ask which one.
        kind: "sale", "purchase", or omit for both.
        payment_status: "paid", "unpaid", "partial", or "outstanding"
            (outstanding = anything not fully paid, i.e. unpaid + partial).
        search: match a transaction number or notes (e.g. "SALE-0042").
        from_date: explicit start date, ISO "YYYY-MM-DD". Overrides days.
        to_date: explicit end date, ISO "YYYY-MM-DD".

    Use for "what did we sell this week", "unpaid bills", "purchases in
    September", or one contact's recent transactions. For a running total or
    net position, use get_business_summary instead.
    """
    contact_id: Optional[int] = None
    if contact_name:
        contact, problem = await resolve_contact(contact_name)
        if problem:
            return problem
        contact_id = contact.id

    txn_type: Optional[TransactionType] = None
    if kind:
        normalized = kind.strip().lower()
        if normalized in ("sale", "sales"):
            txn_type = TransactionType.sale
        elif normalized in ("purchase", "purchases"):
            txn_type = TransactionType.purchase

    # A single payment_status filter can't express "not fully paid", so
    # "outstanding" is handled as a post-filter (unpaid + partial) rather than a
    # DB status match.
    status: Optional[PaymentStatus] = None
    outstanding_only = False
    if payment_status:
        key = payment_status.strip().lower()
        if key in ("outstanding", "pending", "due", "unsettled", "not paid"):
            outstanding_only = True
        elif key == "paid":
            status = PaymentStatus.paid
        elif key in ("partial", "partially", "partially paid"):
            status = PaymentStatus.partial
        elif key == "unpaid":
            status = PaymentStatus.unpaid
        else:
            return (
                f'I don\'t recognise payment status "{payment_status}". '
                "Use paid, unpaid, partial, or outstanding."
            )

    explicit = bool(from_date or to_date)
    from_bound: Optional[date] = None if explicit else _period_start(days)
    to_bound: Optional[date] = None
    if from_date:
        try:
            from_bound = date.fromisoformat(from_date.strip())
        except ValueError:
            return f'Could not read the start date "{from_date}". Use YYYY-MM-DD.'
    if to_date:
        try:
            to_bound = date.fromisoformat(to_date.strip())
        except ValueError:
            return f'Could not read the end date "{to_date}". Use YYYY-MM-DD.'

    filters = TransactionFilterDto(
        type=txn_type,
        payment_status=status,
        contact_id=contact_id,
        from_date=from_bound,
        to_date=to_bound,
        search=search,
    )
    txns = await TransactionsService.list_transactions(filters)

    if outstanding_only:
        txns = [t for t in txns if (t.total_amount - t.paid_amount) > 0]

    if explicit:
        lo = from_bound.isoformat() if from_bound else "start"
        hi = to_bound.isoformat() if to_bound else "today"
        window = f"{lo} to {hi}"
    elif days:
        window = f"last {days} days"
    else:
        window = "all time"

    if not txns:
        return f"No transactions found for {window}."

    txns.sort(key=lambda t: t.transaction_date, reverse=True)
    total = len(txns)
    shown = txns[:MAX_ROWS]

    # Totals are computed here, over *every* matching transaction, not left to
    # the model to add up from the rows below. The row list is capped at
    # MAX_ROWS, so summing it would silently miss the overflow -- and small
    # models can't reliably add many figures anyway. One trustworthy number
    # beats thirty rows the model has to total itself.
    def _totals(items: list) -> tuple[int, Decimal, Decimal]:
        value = sum((t.total_amount for t in items), Decimal(0))
        due = sum(((t.total_amount - t.paid_amount) for t in items), Decimal(0))
        return len(items), value, due

    sales = [t for t in txns if t.type == TransactionType.sale]
    purchases = [t for t in txns if t.type == TransactionType.purchase]

    lines = [f"TRANSACTIONS ({window})"]
    summary = ["SUMMARY:"]
    if sales:
        n, value, due = _totals(sales)
        summary.append(
            f"- Sales: {n} txns, {_inr(value)} total"
            + (f", {_inr(due)} outstanding" if due > 0 else "")
        )
    if purchases:
        n, value, due = _totals(purchases)
        summary.append(
            f"- Purchases: {n} txns, {_inr(value)} total"
            + (f", {_inr(due)} outstanding" if due > 0 else "")
        )
    if len(summary) > 1:
        lines.extend(summary)
        lines.append("")

    for t in shown:
        who = t.contact.name if t.contact else "—"
        outstanding = t.total_amount - t.paid_amount
        tail = (
            f"{t.payment_status.value}"
            if outstanding <= 0
            else f"{t.payment_status.value}, {_inr(outstanding)} due"
        )
        lines.append(
            f"- {t.transaction_date.isoformat()} | {t.transaction_number} | "
            f"{t.type.value} | {who} | {_inr(t.total_amount)} | {tail}"
        )

    note = _truncation_note(total, len(shown))
    if note:
        lines.append(note)

    return "\n".join(lines)
