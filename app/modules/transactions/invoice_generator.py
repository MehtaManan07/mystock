from fpdf import FPDF
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from app.modules.transactions.models import Transaction


class InvoicePDF(FPDF):
    def header(self):
        # Company header
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "MAYUR AGENCY", ln=True, align="C")

        self.set_font("Helvetica", "", 10)
        self.multi_cell(
            0,
            5,
            "Manhar Lodge, Opp., Vegitable Market,\n"
            "Dharmendra Road, RAJKOT.\n"
            "Phone: +91-9930597995",
            align="C",
        )
        self.ln(5)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)

    @staticmethod
    def generate_invoice_pdf(transaction: Transaction) -> bytes:
        """
        Generate a professional invoice PDF using fpdf2.
        Returns PDF bytes (you can upload to S3 or save locally).
        """

        pdf = InvoicePDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", size=11)

        # --- Invoice Header ---
        pdf.cell(0, 8, f"Invoice No: {transaction.transaction_number}", ln=True)
        pdf.cell(
            0, 8, f"Date: {transaction.transaction_date.strftime('%d-%m-%Y')}", ln=True
        )
        pdf.ln(5)

        # --- Customer Info ---
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Bill To:", ln=True)
        pdf.set_font("Helvetica", "", 11)

        customer_lines = [transaction.contact.name]

        # Address
        if getattr(transaction.contact, "address", None):
            customer_lines.append(transaction.contact.address or "")

        # Phone & Email in same line if available
        contact_info = []
        if getattr(transaction.contact, "phone", None):
            contact_info.append(f"Phone: {transaction.contact.phone}")

        if contact_info:
            customer_lines.append(" | ".join(contact_info))

        # Join all lines with newline and print
        pdf.multi_cell(0, 6, "\n".join(customer_lines))
        pdf.ln(8)

        # --- Table Header ---
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(90, 8, "Product", border=1, fill=True)
        pdf.cell(25, 8, "Qty", border=1, align="R", fill=True)
        pdf.cell(35, 8, "Unit Price", border=1, align="R", fill=True)
        pdf.cell(35, 8, "Total", border=1, align="R", fill=True)
        pdf.ln(8)

        # --- Table Items ---
        pdf.set_font("Helvetica", "", 10)
        for item in transaction.items:
            pdf.cell(90, 8, item.product.name, border=1)
            pdf.cell(25, 8, str(item.quantity), border=1, align="R")
            pdf.cell(35, 8, f"{item.unit_price:.2f}", border=1, align="R")
            pdf.cell(35, 8, f"{item.line_total:.2f}", border=1, align="R")
            pdf.ln(8)

        # --- Totals ---
        def add_total_row(label, value, bold=False):
            pdf.set_font("Helvetica", "B" if bold else "", 10)
            pdf.cell(150, 8, label, border=0, align="R")
            pdf.cell(35, 8, f"{value:.2f}", border=1, align="R")
            pdf.ln(8)

        pdf.ln(3)
        add_total_row("Subtotal:", transaction.subtotal)
        add_total_row("Tax:", transaction.tax_amount)
        add_total_row("Discount:", -abs(transaction.discount_amount))
        add_total_row("Total:", transaction.total_amount, bold=True)

        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 10, "Thank you for your business!", align="R")

        return bytes(pdf.output(dest="S"))
