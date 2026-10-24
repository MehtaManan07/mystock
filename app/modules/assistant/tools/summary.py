"""Business-summary tool backed by the same period-aware dashboard as the UI."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from app.modules.dashboard.schemas import DashboardPeriod
from app.modules.dashboard.service import DashboardService

from ._shared import _inr

LABELS = {"get_business_summary": "Pulling up your business summary"}


@tool
async def get_business_summary(
    period: Literal["month", "last_month", "90_days"] = "month",
) -> str:
    """Get dashboard KPIs, current balances, recent activity and oldest open bills.

    Args:
        period: "month" (month to date, default), "last_month", or "90_days".
            Sales, units sold and cash movement use this period, NOT all time.

    Includes an equally long previous-period comparison. Stock and account
    balances are current snapshots across all dates. Net cash movement is not
    profit or a bank balance; standalone PDF bills do not affect these figures.
    Open bills show remaining amounts before unallocated payments/credits.
    Bill age is not overdue status, and the oldest five bills per type are not
    a ranking of contacts by balance. Use contact/product tools for full ledgers
    or individual stock lookups. This tool does not provide all-time financials.
    """
    data = await DashboardService.get_dashboard_data(DashboardPeriod(period))

    stats = data.stats
    current = data.current
    previous = data.previous
    balances = data.balances

    lines = [
        "BUSINESS SUMMARY",
        f"CURRENT INVENTORY (as of {data.as_of})",
        f"- Products: {stats.total_products}",
        f"- Containers: {stats.total_containers}",
        f"- Contacts: {stats.total_contacts}",
        f"- Total units in stock: {stats.total_inventory}",
        "",
        f"PERIOD PERFORMANCE ({data.window.start} to {data.window.end})",
        f"- Sales booked (including tax): {_inr(current.sales)}",
        f"- Number of sales: {current.sale_count}",
        f"- Units sold: {current.units_sold}",
        f"- Money received: {_inr(current.income)}",
        f"- Money spent: {_inr(current.expenses)}",
        f"- Net cash movement (not profit or bank balance): {_inr(current.net_cash)}",
        f"- Active products sold in this period now out of stock: {data.sold_products_out_of_stock}",
        "",
        f"PREVIOUS PERIOD ({data.window.comparison_start} to {data.window.comparison_end})",
        f"- Sales booked (including tax): {_inr(previous.sales)}",
        f"- Units sold: {previous.units_sold}",
        f"- Net cash movement: {_inr(previous.net_cash)}",
        "",
        f"CURRENT ACCOUNT BALANCES (all dates; as of {data.as_of})",
        f"- To collect: {_inr(balances.receivables)} across {balances.receivable_accounts} accounts",
        f"- To pay: {_inr(balances.payables)} across {balances.payable_accounts} accounts",
        f"- Open customer bills: {balances.open_sales_count}",
        f"- Open supplier bills: {balances.open_purchases_count}",
        "Bill balances below are before unallocated payments/credits; age is not overdue status.",
    ]

    if data.recent_transactions:
        lines.append("")
        lines.append("RECENT TRANSACTIONS (latest 5; all dates)")
        for txn in data.recent_transactions:
            who = txn.contact.name if txn.contact else "—"
            lines.append(
                f"- {txn.transaction_number} | {txn.type} | {who} | "
                f"{txn.transaction_date} | {_inr(txn.total_amount)} | {txn.payment_status}"
            )

    for label, bills, total in (
        ("CUSTOMER", balances.oldest_sales, balances.open_sales_count),
        ("SUPPLIER", balances.oldest_purchases, balances.open_purchases_count),
    ):
        if not bills:
            continue
        lines.append("")
        lines.append(f"OLDEST OPEN {label} BILLS (showing {len(bills)} of {total}; all dates)")
        for bill in bills:
            who = bill.contact.name if bill.contact else "—"
            lines.append(
                f"- {bill.transaction_number} | {who} | "
                f"{_inr(bill.balance_due)} still due | {bill.age_days} days old"
            )

    return "\n".join(lines)
