"""
The tools the agent is allowed to call.

A tool is the *only* way the model touches the business. It never sees the
database and never gets raw rows; it asks for a named, typed capability and
gets back a short piece of text it can reason over. That boundary is the whole
safety story for the read layer -- the model cannot query anything we did not
deliberately expose here.

Every tool in this file is READ-ONLY. Writes (issuing a bill, recording a
payment) are a different animal: they go through the human-in-the-loop path and
do not belong here. Keeping reads and writes in separate layers means "can the
agent do this without asking" is answered by *which list the tool is in*, not by
remembering a flag.

DB ACCESS
---------
Tools are async and the database is synchronous, so every tool that reads data
goes through a service whose methods already wrap their work in ``run_db`` --
one hop onto a threadpool, the session opened and closed there, nothing blocking
the event loop. Tools therefore ``await`` a service; they never open a session.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Union

from langchain_core.tools import tool

from app.modules.dashboard.service import DashboardService


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


@tool
async def get_business_summary() -> str:
    """Get a snapshot of the business's current position.

    Returns the headline numbers: how many products, containers and contacts
    exist and total units in stock; total income, total expenses and net
    balance to date; the five most recent transactions; and the contacts with
    the largest outstanding balances (positive means they owe the business,
    negative means the business owes them).

    Use this for any question about overall financial position, totals, recent
    activity, or who owes money. Do not use it for a specific product's stock
    level or a single contact's full ledger -- it is a summary, not a lookup.
    """
    data = await DashboardService.get_dashboard_data()

    stats = data.stats
    fin = data.financial_overview

    lines = [
        "BUSINESS SUMMARY",
        f"- Products: {stats.total_products}",
        f"- Containers: {stats.total_containers}",
        f"- Contacts: {stats.total_contacts}",
        f"- Total units in stock: {stats.total_inventory}",
        "",
        "FINANCIALS (to date)",
        f"- Total income: {_inr(fin.total_income)}",
        f"- Total expenses: {_inr(fin.total_expenses)}",
        f"- Net balance: {_inr(fin.net_balance)}",
    ]

    if data.recent_transactions:
        lines.append("")
        lines.append("RECENT TRANSACTIONS (latest 5)")
        for txn in data.recent_transactions:
            who = txn.contact["name"] if txn.contact else "—"
            lines.append(
                f"- {txn.transaction_number} | {txn.type} | {who} | "
                f"{_inr(txn.total_amount)} | {txn.payment_status}"
            )

    if data.outstanding_contacts:
        lines.append("")
        lines.append("TOP OUTSTANDING BALANCES")
        for contact in data.outstanding_contacts:
            owed = contact.balance
            direction = "owes business" if owed > 0 else "business owes"
            lines.append(
                f"- {contact.name} ({contact.type}): "
                f"{_inr(abs(owed))} ({direction})"
            )

    return "\n".join(lines)


# The tools the agent may call, and the one-line present-tense label the UI
# shows while each runs. The label is user-facing and must read like an action
# ("Pulling up ...") -- never the bare function name, which means nothing to the
# owner and leaks our internals into the chat.
TOOLS = [get_business_summary]

TOOL_LABELS = {
    "get_business_summary": "Pulling up your business summary",
}


def label_for(tool_name: str) -> str:
    """The user-facing chip label for a tool, with a safe generic fallback."""
    return TOOL_LABELS.get(tool_name, "Working on it")
