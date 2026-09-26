"""Compatibility entry point for earlier item specs; archives final PDFs by default.

Use --preview only for an unissued draft. For new specs and historical imports,
prefer `python -m scripts.pdf_invoice`.
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.core.db.engine import SessionLocal
from app.modules.contacts.models import Contact
from app.modules.products.models import Product
from app.modules.pdf_invoices.render import GeneratePdfInvoice
from scripts.pdf_invoice import generate


def convert_spec(spec: dict) -> GeneratePdfInvoice:
    with SessionLocal() as db:
        contacts = db.scalars(select(Contact).where(
            Contact.name.ilike(f"%{spec['buyer']}%"), Contact.deleted_at.is_(None)
        )).all()
        if len(contacts) != 1:
            raise ValueError("Buyer must match exactly one existing contact; use a new-format spec for other buyers")
        contact = contacts[0]
        lines = []
        for item in spec["items"]:
            product = db.get(Product, item["product_id"]) if item.get("product_id") else None
            if item.get("product_id") and product is None:
                raise ValueError(f"Product {item['product_id']} not found")
            rate = item.get("tax_rate")
            if rate is None and product is not None:
                rate = product.gst_rate
            if rate is None:
                rate = spec.get("default_tax_rate")
            if rate is None:
                raise ValueError("Supply each item's applicable GST rate or an explicitly confirmed default")
            lines.append({
                "name": item.get("name") or (product.name if product else None),
                "quantity": item["qty"], "unit_price": item["rate"], "tax_rate": rate,
                "hsn_code": item.get("hsn") or (product.hsn_code if product else None),
            })
        converted = GeneratePdfInvoice(
            invoice_number=spec["invoice_number"], invoice_date=spec["date"],
            customer_name=contact.name, customer_gstin=contact.gstin,
            customer_phone=contact.phone, customer_address=contact.address,
            tax_type=spec["tax_type"], total_amount=spec.get("total_amount"),
            line_items=lines, notes=spec.get("notes"),
        )
        db.rollback()
        return converted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    generate(convert_spec(json.loads(args.spec.read_text())), args.output, args.preview)
