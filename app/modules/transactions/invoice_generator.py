"""
Invoice PDF Generator using ReportLab
Generates professional GST-compliant invoices for transactions.
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from decimal import Decimal
from io import BytesIO


from app.modules.transactions.models import Transaction
from app.modules.settings.models import CompanySettings
from app.modules.vendor_product_skus.models import VendorProductSku
from app.modules.products.models import Product
from app.core.utils import calculate_due_date, amount_to_words, format_invoice_date
from sqlalchemy.orm import Session
from sqlalchemy import and_


class InvoiceGenerator:
    """
    PDF Invoice Generator using ReportLab.
    Generates professional GST-compliant invoices with automatic pagination.
    """

    @staticmethod
    def generate_invoice_pdf(
        transaction: Transaction,
        company_settings: CompanySettings,
        db: Session
    ) -> bytes:
        """
        Generate a professional GST invoice PDF from transaction data.
        
        Args:
            transaction: Transaction model with items, contact, etc.
            company_settings: Company settings with seller information
            db: Database session for vendor SKU lookups
            
        Returns:
            bytes: PDF file contents
        """
        # Create PDF in memory
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Set up margins
        left_margin = 40
        right_margin = width - 40
        top_margin = height - 40
        bottom_margin = 80  # Reserve space for footer

        FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts','DejaVu')
        pdfmetrics.registerFont(TTFont('DejaVuSans', os.path.join(FONTS_DIR, 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', os.path.join(FONTS_DIR, 'DejaVuSans-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Oblique', os.path.join(FONTS_DIR, 'DejaVuSans-Oblique.ttf')))
        
        def draw_header(c, is_first_page=True):
            """Draw the header section"""
            y = top_margin
            
            # ---------- HEADER SECTION ----------
            # Seller details (left side)
            c.setFont("DejaVuSans-Bold", 11)
            c.drawString(left_margin, y, f"Name : {company_settings.seller_name}")
            y -= 15
            
            c.setFont("DejaVuSans", 10)
            c.drawString(left_margin, y, f"Phone : {company_settings.seller_phone}")
            y -= 15
            
            c.drawString(left_margin, y, f"Email : {company_settings.seller_email}")
            y -= 15
            
            c.drawString(left_margin, y, f"GSTIN : {company_settings.seller_gstin}")
            y -= 25
            
            # TAX INVOICE header (right side, aligned with seller details)
            c.setFont("DejaVuSans-Bold", 12)
            invoice_text = "TAX INVOICE"
            invoice_width = c.stringWidth(invoice_text, "DejaVuSans-Bold", 12)
            c.drawString(right_margin - invoice_width, top_margin, invoice_text)
            
            c.setFont("DejaVuSans", 9)
            original_text = "ORIGINAL FOR RECIPIENT"
            original_width = c.stringWidth(original_text, "DejaVuSans", 9)
            c.drawString(right_margin - original_width, top_margin - 15, original_text)
            
            if is_first_page:
                # ---------- CUSTOMER DETAILS SECTION ----------
                y -= 5
                
                # Customer Detail heading with border
                c.setFont("DejaVuSans-Bold", 10)
                c.setFillColor(colors.lightgrey)
                c.rect(left_margin, y - 15, right_margin - left_margin, 18, fill=1, stroke=1)
                c.setFillColor(colors.black)
                c.drawString(left_margin + 5, y - 10, "Customer Detail")
                y -= 25
                
                # Customer information
                c.setFont("DejaVuSans-Bold", 10)
                c.drawString(left_margin, y, f"M/S {transaction.contact.name}")
                y -= 15
                
                c.setFont("DejaVuSans", 9)
                # Handle None address
                customer_address = transaction.contact.address or "-"
                c.drawString(left_margin, y, f"Address {customer_address}")
                y -= 13
                
                # Handle None phone
                customer_phone = transaction.contact.phone or "-"
                c.drawString(left_margin, y, f"Phone {customer_phone}")
                y -= 13
                
                # Handle None GSTIN
                customer_gstin = transaction.contact.gstin or "-"
                c.drawString(left_margin, y, f"GSTIN {customer_gstin}")
                y -= 20
                
                # ---------- COMPANY DETAILS (Small box) ----------
                c.setFont("DejaVuSans-Bold", 9)
                c.drawString(left_margin, y, company_settings.company_name)
                y -= 12
                
                c.setFont("DejaVuSans", 8)
                c.drawString(left_margin, y, company_settings.company_address_line1)
                y -= 10
                
                c.drawString(left_margin, y, company_settings.company_address_line2)
                y -= 10
                
                c.drawString(left_margin, y, company_settings.company_address_line3)
                y -= 20
                
                # ---------- INVOICE INFO ----------
                # Draw these on the right side
                invoice_y = y + 60  # Position relative to customer details
                
                c.setFont("DejaVuSans", 9)
                invoice_no = transaction.transaction_number
                invoice_date = format_invoice_date(transaction.transaction_date)
                due_date_obj = calculate_due_date(transaction.transaction_date)
                due_date = format_invoice_date(due_date_obj)
                
                c.drawString(right_margin - 250, invoice_y, f"Invoice No. {invoice_no}")
                c.drawString(right_margin - 120, invoice_y, f"Invoice Date {invoice_date}")
                invoice_y -= 15
                
                c.drawString(right_margin - 250, invoice_y, f"Due Date {due_date}")
                
                y -= 20
            
            return y
        
        # Draw first page header
        y = draw_header(c, is_first_page=True)
        
        # ---------- ITEMS TABLE WITH PAGINATION ----------
        # Prepare table header
        table_header = [
            ['Sr.\nNo.', 'SKU / Description', 'HSN / SAC', 'Qty', 'Rate', 
             'Taxable Value', 'IGST\n%', 'IGST\nAmount', 'Total']
        ]
        
        col_widths = [30, 140, 60, 40, 50, 70, 40, 50, 60]
        
        # Calculate totals and prepare items data
        items_data = []
        total_qty = Decimal('0')
        total_taxable = Decimal('0')
        total_igst = Decimal('0')
        total_amount = Decimal('0')
        
        for item in transaction.items:
            # Calculate taxable value (back-calculate from line_total assuming 18% GST)
            # line_total = taxable_value * 1.18
            # taxable_value = line_total / 1.18
            taxable_value = item.line_total / Decimal('1.18')
            igst_amount = item.line_total - taxable_value
            
            # Get vendor SKU (fallback to company SKU, then product name)
            # Try to get vendor-specific SKU
            vendor_sku_mapping = db.query(VendorProductSku).filter(
                and_(
                    VendorProductSku.product_id == item.product_id,
                    VendorProductSku.vendor_id == transaction.contact_id,
                    VendorProductSku.deleted_at.is_(None),
                )
            ).first()
            
            if vendor_sku_mapping:
                sku_display = vendor_sku_mapping.vendor_sku
            elif item.product.company_sku:
                sku_display = item.product.company_sku
            else:
                sku_display = item.product.name
            
            items_data.append({
                'name': sku_display,
                'hsn': company_settings.hsn_code,
                'qty': item.quantity,
                'rate': float(item.unit_price),
                'taxable': float(taxable_value),
                'igst_percent': 18.0,
                'igst_amount': float(igst_amount),
                'total': float(item.line_total)
            })
            
            total_qty += item.quantity
            total_taxable += taxable_value
            total_igst += igst_amount
            total_amount += item.line_total
        
        # Process items in chunks that fit on each page
        items_per_page_first = 20  # First page has less space due to header
        items_per_page_continuation = 35  # Continuation pages have more space
        
        item_index = 0
        page_number = 1
        
        while item_index < len(items_data):
            if page_number > 1:
                # Start new page
                c.showPage()
                y = draw_header(c, is_first_page=False)
            
            # Determine how many items to show on this page
            items_on_this_page = items_per_page_first if page_number == 1 else items_per_page_continuation
            end_index = min(item_index + items_on_this_page, len(items_data))
            
            # Build table data for this page
            table_data = table_header.copy()
            
            for idx in range(item_index, end_index):
                item = items_data[idx]
                table_data.append([
                    str(idx + 1),
                    item['name'],
                    item['hsn'],
                    f"{item['qty']:.2f}",
                    f"{item['rate']:.2f}",
                    f"{item['taxable']:.2f}",
                    f"{item['igst_percent']:.2f}",
                    f"{item['igst_amount']:.2f}",
                    f"{item['total']:.2f}"
                ])
            
            # Add total row only on the last page
            if end_index == len(items_data):
                table_data.append([
                    '',
                    'Total',
                    '',
                    f"{float(total_qty):.2f}",
                    '',
                    f"{float(total_taxable):.2f}",
                    '',
                    f"{float(total_igst):.2f}",
                    f"{float(total_amount):.2f}"
                ])
            
            # Create and style table
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTNAME', (0, -1), (-1, -1), 'DejaVuSans-Bold'),
            ]))
            
            # Draw table
            table_width, table_height = table.wrapOn(c, width, height)
            table.drawOn(c, left_margin, y - table_height)
            y = y - table_height - 20
            
            item_index = end_index
            page_number += 1
        
        # ---------- AMOUNT IN WORDS ----------
        # Only draw footer on the last page
        c.setFont("DejaVuSans-Bold", 9)
        c.drawString(left_margin, y, "Total in words")
        y -= 15
        
        c.setFont("DejaVuSans", 9)
        words = amount_to_words(total_amount)
        c.drawString(left_margin, y, words)
        y -= 25
        
        # ---------- TERMS AND CONDITIONS ----------
        c.setFont("DejaVuSans-Bold", 9)
        c.drawString(left_margin, y, "Terms and Conditions")
        y -= 15
        
        c.setFont("DejaVuSans", 8)
        terms = company_settings.terms_and_conditions.split('\n')
        
        for term in terms:
            if term.strip():  # Skip empty lines
                c.drawString(left_margin, y, term.strip())
                y -= 12
        
        # ---------- SUMMARY BOX (Right side) ----------
        summary_y = y + 70
        summary_x = right_margin - 200
        
        c.setFont("DejaVuSans", 9)
        c.drawString(summary_x, summary_y, f"Taxable Amount")
        c.drawString(summary_x + 120, summary_y, f"{float(total_taxable):.2f}")
        summary_y -= 15
        
        c.drawString(summary_x, summary_y, f"Add : IGST")
        c.drawString(summary_x + 120, summary_y, f"{float(total_igst):.2f}")
        summary_y -= 15
        
        c.drawString(summary_x, summary_y, f"Total Tax")
        c.drawString(summary_x + 120, summary_y, f"{float(total_igst):.2f}")
        summary_y -= 15
        
        c.setFont("DejaVuSans-Bold", 10)
        c.drawString(summary_x, summary_y, f"Total Amount")
        c.drawString(summary_x + 120, summary_y, f"₹{float(total_amount):.2f}")
        summary_y -= 20
        
        c.setFont("DejaVuSans-Oblique", 8)
        c.drawString(summary_x, summary_y, "(E & O.E.)")
        
        # ---------- FOOTER ----------
        y -= 30
        
        c.setFont("DejaVuSans", 8)
        c.drawString(left_margin, y, "Certified that the particulars given above are true and correct.")
        y -= 25
        
        c.setFont("DejaVuSans-Bold", 9)
        c.drawString(left_margin, y, f"For {company_settings.company_name}")
        y -= 35
        
        c.setFont("DejaVuSans", 8)
        signature_x = right_margin - 150
        c.drawString(signature_x, y, "Authorised Signatory")
        
        # Save PDF
        c.save()
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
