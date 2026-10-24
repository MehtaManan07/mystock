"""Business-summary tool: the overall-position snapshot."""

from __future__ import annotations

from langchain_core.tools import tool

from app.modules.dashboard.service import DashboardService

from ._shared import _inr

LABELS = {"get_business_summary": "Pulling up your business summary"}


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
