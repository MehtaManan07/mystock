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
from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.modules.payments.schemas import FilterManualPaymentsDto
from app.modules.payments.service import PaymentsService
from app.modules.transactions.schemas import TransactionFilterDto
from app.modules.transactions.service import TransactionsService

from app.modules.assistant.tools._shared import MAX_ROWS, _inr, _period_start, _truncation_note
from app.modules.assistant.tools.contacts import resolve_contact

LABELS = {"get_contact_ledger": "Opening the ledger"}


@dataclass
class _Entry:
    on: date
    text: str


@tool
async def get_contact_ledger(customer: str, days: Optional[int] = None) -> str:
    """One customer's ledger: recent bills and payments, with what they owe.

    Args:
        customer: customer or supplier name/phone. If it matches more than one
            contact, this returns the choices so you can ask which one.
        days: rolling window, how far back to look. Omit for all time.

    Use for "how do we stand with X", "show Dindayal's account", or "what has X
    bought and paid lately". Balance sign: positive means the customer owes the
    business; negative means the business owes them.
    """
    contact, problem = await resolve_contact(customer)
    if problem:
        return problem
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
                text=(
                    f"{t.transaction_date.isoformat()} | bill {t.transaction_number} "
                    f"| {t.type.value} | {_inr(t.total_amount)} | {t.payment_status.value}"
                ),
            )
        )
    for p in payments:
        direction = "received" if p.type == "income" else "paid out"
        method = p.payment_method.value if p.payment_method else "?"
        entries.append(
            _Entry(
                on=p.payment_date,
                text=(
                    f"{p.payment_date.isoformat()} | payment {direction} "
                    f"| {_inr(p.amount)} | via {method}"
                ),
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
    header = f"LEDGER for {contact.name} ({window}) -- balance: {standing}"

    if not entries:
        return header + "\nNo bills or payments in this period."

    entries.sort(key=lambda e: e.on, reverse=True)
    total = len(entries)
    shown = entries[:MAX_ROWS]

    lines = [header, ""]
    lines.extend(f"- {e.text}" for e in shown)

    note = _truncation_note(total, len(shown))
    if note:
        lines.append(note)

    return "\n".join(lines)
