"""Product-buyers tool: which customers bought a product, ranked by quantity.

"Who buys the most Mor Kankavati" is a product -> customers question, and none
of the other read tools can answer it: ``get_transactions`` filters by contact
or date but not by product line item, and ``find_products`` only knows stock.
This tool resolves the product, then asks the backend to aggregate sale line
items by customer -- the ranking is computed in SQL, so the model never adds up
rows and never sees the individual sales.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool

from app.modules.products.service import ProductService
from app.modules.transactions.service import TransactionsService

from app.modules.assistant.tools._shared import MAX_ROWS, _inr, _period_start, _truncation_note
from app.modules.assistant.widgets import TableCell, TableColumn, TableWidget

LABELS = {"get_product_buyers": "Finding who bought this product"}


def _product_label(p: dict) -> str:
    return p.get("display_name") or p.get("name") or f"product #{p['id']}"


@tool(response_format="content_and_artifact")
async def get_product_buyers(
    product: str, days: Optional[int] = None
) -> tuple[str, Optional[dict]]:
    """Which customers bought a product, and how much, ranked by quantity.

    Args:
        product: product name/size/SKU to look up (e.g. "mor kankavati",
            "pagla 3 inch"). If it matches more than one product, this returns
            the choices so you can ask which one is meant.
        days: rolling window, how far back to look. Omit for all time.

    Use for "who bought the most X", "which customers purchased X", or "who has
    been buying X lately". Only sales count -- this is about customers buying the
    product, not stock purchased from suppliers. For a product's stock or price
    use find_products; for one customer's whole account use get_contact_ledger.

    The buyers are shown to the user as a ranked table; you receive only a
    one-line summary naming the top buyer, so lead with that and do not re-list
    the table.
    """
    matches = await ProductService.find_all(search=product)
    if not matches:
        return f'No product found matching "{product}".', None
    if len(matches) > 1:
        names = ", ".join(_product_label(p) for p in matches[:MAX_ROWS])
        return (
            f'"{product}" matches several products: {names}. '
            "Ask which one is meant, then look again with a more specific name.",
            None,
        )

    prod = matches[0]
    name = _product_label(prod)
    from_bound = _period_start(days)
    window = f"last {days} days" if days else "all time"

    buyers = await TransactionsService.product_buyers(prod["id"], from_bound)
    if not buyers:
        return f"No customer has bought {name} ({window}).", None

    total = len(buyers)
    shown = buyers[:MAX_ROWS]
    total_qty = sum(b.quantity for b in buyers)
    total_value = sum((b.amount for b in buyers), Decimal(0))
    top = buyers[0]

    widget = TableWidget(
        title=f"Buyers of {name} ({window})",
        summary=(
            f"{total} customer(s) \u00b7 {total_qty} units \u00b7 "
            f"{_inr(total_value)} total"
        ),
        columns=[
            TableColumn(label="Customer"),
            TableColumn(label="Units", align="right"),
            TableColumn(label="Value", align="right"),
            TableColumn(label="Bills", align="right"),
        ],
        rows=[
            [
                TableCell(text=b.contact_name, href=f"/contacts/{b.contact_id}"),
                TableCell(text=str(b.quantity)),
                TableCell(text=_inr(b.amount)),
                TableCell(text=str(b.transaction_count)),
            ]
            for b in shown
        ],
        truncation_note=_truncation_note(total, len(shown)) or None,
    )

    content = (
        f"Displayed buyers of {name} ({window}), ranked by units. Top buyer: "
        f"{top.contact_name} with {top.quantity} units. {total} customer(s), "
        f"{total_qty} units total. Lead with the top buyer in one sentence; do "
        "not re-list the table."
    )
    return content, widget.model_dump()
