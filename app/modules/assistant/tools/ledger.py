"""Contact ledger tool: one customer's recent bills and payments together.

"What's going on with Dindayal" is a timeline question -- bills raised and money
received, interleaved, against the balance they still owe. Transactions and
payments live in separate tables; this tool merges them into one date-ordered
ledger and leads with the current outstanding balance so the model answers "how
do we stand with X" without stitching two tools together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from langchain_core.tools import tool

from app.modules.payments.schemas import FilterManualPaymentsDto
from app.modules.payments.service import PaymentsService
from app.modules.transactions.schemas import TransactionFilterDto
from app.modules.transactions.service import TransactionsService

from app.modules.assistant.tools._shared import MAX_ROWS, _inr, _period_start, _truncation_note
from app.modules.assistant.tools.contacts import resolve_contact
from app.modules.assistant.widgets import TableCell, TableColumn, TableWidget

LABELS = {"get_contact_ledger": "Opening the ledger"}


@dataclass
class _Entry:
    on: date
    desc: str
    href: Optional[str]
    amount: str
    detail: str


@tool(response_format="content_and_artifact")
async def get_contact_ledger(
    customer: str, days: Optional[int] = None
) -> tuple[str, Optional[dict]]:
    """One customer's ledger: recent bills and payments, with what they owe.

    Args:
        customer: customer or supplier name/phone. If it matches more than one
            contact, this returns the choices so you can ask which one.
        days: rolling window, how far back to look. Omit for all time.

    Use for "how do we stand with X", "show Dindayal's account", or "what has X
    bought and paid lately". Balance sign: positive means the customer owes the
    business; negative means the business owes them.

    The bills and payments are shown to the user as a table; you receive only a
    one-line summary leading with the balance, so state the balance in a
    sentence and do not re-list the entries.
    """
    contact, problem = await resolve_contact(customer)
    if problem:
        return problem, None
    assert contact is not None  # resolve_contact returns one when problem is None

    from_bound = _period_start(days)

    txns = await TransactionsService.list_transactions(
        TransactionFilterDto(
            type=None,
            payment_status=None,
            contact_id=contact.id,
            from_date=from_bound,
            to_date=None,
            search=None,
        )
    )
    payments = await PaymentsService.find_all(
        FilterManualPaymentsDto(
            type=None,
            category=None,
            payment_method=None,
            contact_id=contact.id,
            transaction_id=None,
            from_date=from_bound,
            to_date=None,
            search=None,
            min_amount=None,
            max_amount=None,
            manual_only=None,
        )
    )

    entries: list[_Entry] = []
    for t in txns:
        entries.append(
            _Entry(
                on=t.transaction_date,
                desc=f"Bill {t.transaction_number}",
                href=f"/transactions/{t.id}",
                amount=_inr(t.total_amount),
                detail=f"{t.type.value} \u00b7 {t.payment_status.value}",
            )
        )
    for p in payments:
        direction = "received" if p.type == "income" else "paid out"
        method = p.payment_method.value if p.payment_method else "?"
        entries.append(
            _Entry(
                on=p.payment_date,
                desc=f"Payment {direction}",
                href=None,
                amount=_inr(p.amount),
                detail=f"via {method}",
            )
        )

    bal = contact.balance
    if bal > 0:
        standing = f"{_inr(bal)} owed to the business"
    elif bal < 0:
        standing = f"{_inr(abs(bal))} owed by the business"
    else:
        standing = "settled"

    window = f"last {days} days" if days else "all time"

    if not entries:
        return (
            f"Ledger for {contact.name} ({window}) -- balance: {standing}. "
            "No bills or payments in this period.",
            None,
        )

    entries.sort(key=lambda e: e.on, reverse=True)
    total = len(entries)
    shown = entries[:MAX_ROWS]

    widget = TableWidget(
        title=f"Ledger for {contact.name} ({window})",
        summary=f"Balance: {standing}",
        columns=[
            TableColumn(label="Date"),
            TableColumn(label="Entry"),
            TableColumn(label="Amount", align="right"),
            TableColumn(label="Detail"),
        ],
        rows=[
            [
                TableCell(text=e.on.isoformat()),
                TableCell(text=e.desc, href=e.href),
                TableCell(text=e.amount),
                TableCell(text=e.detail),
            ]
            for e in shown
        ],
        truncation_note=_truncation_note(total, len(shown)) or None,
    )

    content = (
        f"Displayed {contact.name}'s ledger ({window}): {total} entries, "
        f"balance {standing}. Lead with the balance in one sentence; do not "
        "re-list the entries."
    )
    return content, widget.model_dump()
