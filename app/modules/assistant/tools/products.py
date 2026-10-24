"""Product lookup tool: stock level, price and SKU."""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from app.modules.products.service import ProductService

from ._shared import LOW_STOCK_THRESHOLD, MAX_ROWS, _inr, _truncation_note

LABELS = {"find_products": "Looking up products and stock"}


@tool
async def find_products(
    search: Optional[str] = None, low_stock_only: bool = False
) -> str:
    """Look up products: their sale price, SKU, and how many units are in stock.

    Args:
        search: words to match against name, size, packing or SKU
            (e.g. "pagla 3 inch"). Leave empty to list the catalogue.
        low_stock_only: if true, return only products at or below the low-stock
            threshold (10 units) -- use for "what is running low / needs reorder".

    Use for a single product's stock level, its price or SKU, or which products
    are low. Do not use for overall totals -- that is get_business_summary.
    """
    products = await ProductService.find_all(search=search)

    if low_stock_only:
        products = [p for p in products if p["totalQuantity"] <= LOW_STOCK_THRESHOLD]
        products.sort(key=lambda p: p["totalQuantity"])

    if not products:
        where = f' matching "{search}"' if search else ""
        extra = " at or below the low-stock level" if low_stock_only else ""
        return f"No products found{where}{extra}."

    total = len(products)
    shown = products[:MAX_ROWS]

    header = "LOW STOCK PRODUCTS" if low_stock_only else "PRODUCTS"
    lines = [header]
    for p in shown:
        name = p.get("display_name") or p.get("name") or "—"
        bits = [f"{name} | {p['totalQuantity']} in stock"]
        if p.get("company_sku"):
            bits.append(f"SKU {p['company_sku']}")
        if p.get("default_sale_price") is not None:
            bits.append(f"sale {_inr(p['default_sale_price'])}")
        lines.append("- " + " | ".join(bits))

    note = _truncation_note(total, len(shown))
    if note:
        lines.append(note)

    return "\n".join(lines)
