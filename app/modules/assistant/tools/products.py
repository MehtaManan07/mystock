"""Product lookup tool: stock level, price and SKU."""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from app.modules.products.service import ProductService

from app.modules.assistant.tools._shared import LOW_STOCK_THRESHOLD, MAX_ROWS, _inr, _truncation_note
from app.modules.assistant.widgets import TableCell, TableColumn, TableWidget

LABELS = {"find_products": "Looking up products and stock"}


@tool(response_format="content_and_artifact")
async def find_products(
    search: Optional[str] = None, low_stock_only: bool = False
) -> tuple[str, Optional[dict]]:
    """Look up products: their sale price, SKU, and how many units are in stock.

    Args:
        search: words to match against name, size, packing or SKU
            (e.g. "pagla 3 inch"). Leave empty to list the catalogue.
        low_stock_only: if true, return only products at or below the low-stock
            threshold (10 units) -- use for "what is running low / needs reorder".

    Use for a single product's stock level, its price or SKU, or which products
    are low. Do not use for overall totals -- that is get_business_summary.

    Matches are shown to the user as a table; you receive only a one-line
    summary, so lead with a short sentence and do not re-list the rows.
    """
    products = await ProductService.find_all(search=search)

    if low_stock_only:
        products = [p for p in products if p["totalQuantity"] <= LOW_STOCK_THRESHOLD]
        products.sort(key=lambda p: p["totalQuantity"])

    if not products:
        where = f' matching "{search}"' if search else ""
        extra = " at or below the low-stock level" if low_stock_only else ""
        return f"No products found{where}{extra}.", None

    total = len(products)
    shown = products[:MAX_ROWS]
    kind = "Low-stock products" if low_stock_only else "Products"

    widget = TableWidget(
        title=f"{kind}" + (f' matching "{search}"' if search else ""),
        summary=f"{total} product(s)",
        columns=[
            TableColumn(label="Product"),
            TableColumn(label="In stock", align="right"),
            TableColumn(label="SKU"),
            TableColumn(label="Sale price", align="right"),
        ],
        rows=[
            [
                TableCell(text=p.get("display_name") or p.get("name") or "\u2014"),
                TableCell(text=str(p["totalQuantity"])),
                TableCell(text=p.get("company_sku") or "\u2014"),
                TableCell(
                    text=_inr(p["default_sale_price"])
                    if p.get("default_sale_price") is not None
                    else "\u2014"
                ),
            ]
            for p in shown
        ],
        truncation_note=_truncation_note(total, len(shown)) or None,
    )

    summary = (
        f"Displayed a table of {total} {kind.lower()}"
        + (f' matching "{search}"' if search else "")
        + ". Lead with one short sentence; do not re-list the rows."
    )
    return summary, widget.model_dump()
