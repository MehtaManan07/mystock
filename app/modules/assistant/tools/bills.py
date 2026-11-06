"""Unified bills tool: every invoice for a customer, across both bill stores.

To the shop owner "a bill" is one idea, but in the data it lives in two tables:
a sale generates a bill (``transactions``) and a bill can also be an uploaded /
archived PDF (``pdf_invoices``). "All of X's bills" is the *union* of both.
Exposing two tools and hoping the model merges them would often yield a
confidently partial list -- the worst failure for a money app -- so the split is
hidden behind this one tool. Both tables draw numbers from one shared sequence
(``SALE-NNNN``, unique across both), so the union needs no de-duplication and
sorts cleanly by bill number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.modules.pdf_invoices.service import PdfInvoiceService
from app.modules.transactions.models import TransactionType
from app.modules.transactions.schemas import TransactionFilterDto
from app.modules.transactions.service import TransactionsService

from app.modules.assistant.tools._shared import MAX_ROWS, _inr, _period_start, _truncation_note
from app.modules.assistant.tools.contacts import resolve_contact
from app.modules.assistant.widgets import TableCell, TableColumn, TableWidget

LABELS = {"find_bills": "Gathering bills"}

# Pull every candidate PDF invoice in one read, then keep this contact's own.
# The shop's archive is small, and a single page keeps the union complete --
# paging risks dropping a bill, the one thing this tool must never do.
_PDF_PAGE_SIZE = 1000


@dataclass
class _Bill:
    number: str
    on: date
    customer: str
    total: Decimal
    source: str
    # In-app link to the bill, opened in a new tab by the chat's markdown
    # renderer. Sales deep-link to the transaction page; archived PDFs open
    # their preview on the PDF Bills page. Both routes are bearer-authed in the
    # SPA, so we never link straight at a PDF endpoint (that would 401 in a new
    # tab). May be empty if a bill has no viewable page.
    href: str


def _sort_key(number: str) -> int:
    """The numeric part of ``SALE-NNNN``, so newest-first sorts by the sequence."""
    match = re.search(r"(\d+)$", number)
    return int(match.group(1)) if match else 0


@tool(response_format="content_and_artifact")
async def find_bills(
    customer: str,
    days: Optional[int] = None,
    source: Optional[str] = None,
) -> tuple[str, Optional[dict]]:
    """List every bill for one customer -- both sales and archived PDF invoices.

    Args:
        customer: customer name or phone. If it matches more than one contact,
            this returns the choices instead of bills so you can ask which one.
        days: rolling window, how far back to look. Omit for all time.
        source: "sale" for only sale-generated bills, "pdf" for only uploaded/
            archived PDFs, or omit for both.

    Use for "give me all of X's bills", "show Dabster's invoices", or "which
    bills did we raise for X this month". For totals/running balance use
    get_business_summary; for payment status detail use get_transactions.

    The itemised bills are shown to the user directly as a table (with links);
    you receive only a one-line summary, so lead with a short sentence and do
    not try to re-list the rows.
    """
    contact, problem = await resolve_contact(customer)
    if problem:
        return problem, None
    assert contact is not None  # resolve_contact returns one when problem is None

    want = source.strip().lower() if source else None
    if want in ("pdf", "archived", "uploaded"):
        want = "pdf"
    elif want in ("sale", "sales", "transaction"):
        want = "sale"
    elif want is not None:
        return (
            f'I don\'t recognise source "{source}". '
            "Use sale, pdf, or omit it for both.",
            None,
        )

    from_bound = _period_start(days)

    bills: list[_Bill] = []

    if want in (None, "sale"):
        txns = await TransactionsService.list_transactions(
            TransactionFilterDto(
                type=TransactionType.sale,
                payment_status=None,
                contact_id=contact.id,
                from_date=from_bound,
                to_date=None,
                search=None,
            )
        )
        for t in txns:
            bills.append(
                _Bill(
                    number=t.transaction_number,
                    on=t.transaction_date,
                    customer=t.contact.name if t.contact else contact.name,
                    total=t.total_amount,
                    source="sale",
                    href=f"/transactions/{t.id}",
                )
            )

    if want in (None, "pdf"):
        page = await PdfInvoiceService.list_invoices(
            page=1,
            page_size=_PDF_PAGE_SIZE,
            search=None,
            from_date=from_bound,
            to_date=None,
        )
        for inv in page.items:
            if inv.customer_id != contact.id:
                continue
            bills.append(
                _Bill(
                    number=inv.invoice_number,
                    on=inv.invoice_date,
                    customer=inv.customer_name,
                    total=inv.total_amount,
                    source="archived PDF",
                    href=f"/pdf-invoices?preview={inv.id}",
                )
            )

    window = f"last {days} days" if days else "all time"
    if not bills:
        return f"No bills found for {contact.name} ({window}).", None

    bills.sort(key=lambda b: _sort_key(b.number), reverse=True)
    total = len(bills)
    shown = bills[:MAX_ROWS]
    grand = sum((b.total for b in bills), Decimal(0))

    # The authoritative table the user sees. Its rows never reach the model --
    # they ride on the tool artifact and React draws them verbatim, so the
    # numbers and links cannot be miscounted, restyled or dropped.
    widget = TableWidget(
        title=f"Bills for {contact.name} ({window})",
        summary=f"{total} bills \u00b7 {_inr(grand)} total",
        columns=[
            TableColumn(label="Bill"),
            TableColumn(label="Date"),
            TableColumn(label="Amount", align="right"),
            TableColumn(label="Source"),
        ],
        rows=[
            [
                TableCell(text=b.number, href=b.href or None),
                TableCell(text=b.on.isoformat()),
                TableCell(text=_inr(b.total)),
                TableCell(text=b.source),
            ]
            for b in shown
        ],
        truncation_note=_truncation_note(total, len(shown)) or None,
    )

    # The model sees only this one line -- enough to write an accurate lead,
    # nothing it could leak or get wrong about the individual bills.
    summary = (
        f"Displayed a table of {total} bill(s) for {contact.name} ({window}), "
        f"{_inr(grand)} total. Lead with one short sentence; do not re-list rows."
    )
    return summary, widget.model_dump()
