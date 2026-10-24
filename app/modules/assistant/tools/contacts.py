"""Contact lookup tool: phone, type and outstanding balance."""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from app.modules.contacts.schemas import FilterContactsDto
from app.modules.contacts.service import ContactsService

from ._shared import MAX_ROWS, _inr, _truncation_note

LABELS = {"find_contacts": "Looking up contacts and balances"}


@tool
async def find_contacts(
    search: Optional[str] = None, owes_money_only: bool = False
) -> str:
    """Look up customers and suppliers: their phone, type and outstanding balance.

    Balance sign: positive means they owe the business; negative means the
    business owes them.

    Args:
        search: name or phone to match (e.g. "Dindayal").
        owes_money_only: if true, return only contacts who owe the business
            (positive balance) -- use for "who owes us money".

    Use for a contact's balance ("how much does X owe"), their phone, or to
    check whether a customer/supplier exists.
    """
    filters = FilterContactsDto(
        search=search,
        balance="positive" if owes_money_only else None,
    )
    contacts = await ContactsService.find_all(filters)

    if not contacts:
        where = f' matching "{search}"' if search else ""
        extra = " who owe the business" if owes_money_only else ""
        return f"No contacts found{where}{extra}."

    total = len(contacts)
    shown = contacts[:MAX_ROWS]

    lines = ["CONTACTS"]
    for c in shown:
        bal = c.balance
        if bal > 0:
            money = f"{_inr(bal)} (owes business)"
        elif bal < 0:
            money = f"{_inr(abs(bal))} (business owes)"
        else:
            money = "settled"
        bits = [c.name, c.type.value, c.phone, money]
        if c.gstin:
            bits.append(f"GSTIN {c.gstin}")
        lines.append("- " + " | ".join(bits))

    note = _truncation_note(total, len(shown))
    if note:
        lines.append(note)

    return "\n".join(lines)
