"""
Invoice PDF Generator using ReportLab
Generates professional GST-compliant invoices for transactions.
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from decimal import Decimal
from io import BytesIO


from app.modules.transactions.models import Transaction, ProductDetailsDisplayMode
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

        sku_cell_style = ParagraphStyle(
            'SkuCell',
            fontName='DejaVuSans',
            fontSize=8,
            leading=10,
        )
        sku_cell_bold_style = ParagraphStyle(
            'SkuCellBold',
            fontName='DejaVuSans-Bold',
            fontSize=8,
            leading=10,
        )
        
        def wrap_text(text, max_width, font_name, font_size):
            """
            Wrap text to fit within max_width, returning a list of lines.
            
            Args:
                text: Text to wrap
                max_width: Maximum width in points
                font_name: Font name
                font_size: Font size
                
            Returns:
                List of text lines
            """
            if not text:
                return [""]
            
            words = text.split()
            lines = []
            current_line = []
            current_width = 0
            
            for word in words:
                # Calculate width of word with space
                word_width = c.stringWidth(word + " ", font_name, font_size)
                word_width_only = c.stringWidth(word, font_name, font_size)
                
                # If single word is longer than max_width, add it anyway (will be truncated by PDF)
                if word_width_only > max_width:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = []
                        current_width = 0
                    lines.append(word)
                    continue
                
                if current_width + word_width <= max_width:
                    current_line.append(word)
                    current_width += word_width
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
                    current_width = word_width
            
            if current_line:
                lines.append(" ".join(current_line))
            
            return lines if lines else [text]

        def extract_state_from_gstin(gstin: str) -> tuple:
            """
            Extract state code and name from GSTIN.
            Returns tuple of (state_name, state_code).
            """
            if not gstin or len(gstin) < 2:
                return ("Not Specified", "00")

            state_code = gstin[:2]

            # Mapping of GST state codes to state names
            state_map = {
                "01": "Jammu and Kashmir",
                "02": "Himachal Pradesh",
                "03": "Punjab",
                "04": "Chandigarh",
                "05": "Uttarakhand",
                "06": "Haryana",
                "07": "Delhi",
                "08": "Rajasthan",
                "09": "Uttar Pradesh",
                "10": "Bihar",
                "11": "Sikkim",
                "12": "Arunachal Pradesh",
                "13": "Nagaland",
                "14": "Manipur",
                "15": "Mizoram",
                "16": "Tripura",
                "17": "Meghalaya",
                "18": "Assam",
                "19": "West Bengal",
                "20": "Jharkhand",
                "21": "Odisha",
                "22": "Chhattisgarh",
                "23": "Madhya Pradesh",
                "24": "Gujarat",
                "25": "Daman and Diu",
                "26": "Dadra and Nagar Haveli",
                "27": "Maharashtra",
                "29": "Karnataka",
                "30": "Goa",
                "32": "Kerala",
                "33": "Tamil Nadu",
                "34": "Puducherry",
                "36": "Telangana",
                "37": "Andhra Pradesh",
            }

            state_name = state_map.get(state_code, "Unknown")
            return (state_name, state_code)

        def draw_header(c, is_first_page=True):
            """Draw the header section with updated layout"""
            y = top_margin

            # ---------- HEADER SECTION ----------
            # Company name prominent at top (14pt bold, uppercase)
            c.setFont("DejaVuSans-Bold", 14)
            c.drawString(left_margin, y, company_settings.company_name.upper())
            y -= 18

            # Company address (3 lines, 9pt)
            c.setFont("DejaVuSans", 9)
            c.drawString(left_margin, y, company_settings.company_address_line1)
            y -= 12
            c.drawString(left_margin, y, company_settings.company_address_line2)
            y -= 12
            c.drawString(left_margin, y, company_settings.company_address_line3)
            y -= 18

            # Extract seller state from GSTIN
            seller_state_name, seller_state_code = extract_state_from_gstin(company_settings.seller_gstin)

            # GSTIN/UIN and State on one line
            c.setFont("DejaVuSans", 9)
            c.drawString(left_margin, y, f"GSTIN/UIN: {company_settings.seller_gstin}")
            c.drawString(left_margin + 200, y, f"Phone: {company_settings.seller_phone}")
            y -= 12

            # State information and Email
            c.drawString(left_margin, y, f"State Name: {seller_state_name}, Code: {seller_state_code}")
            c.drawString(left_margin + 200, y, f"Email: {company_settings.seller_email}")
            y -= 25

            # TAX INVOICE header (right side, aligned at top)
            c.setFont("DejaVuSans-Bold", 12)
            invoice_text = "TAX INVOICE"
            invoice_width = c.stringWidth(invoice_text, "DejaVuSans-Bold", 12)
            c.drawString(right_margin - invoice_width, top_margin, invoice_text)

            c.setFont("DejaVuSans", 9)
            original_text = "ORIGINAL FOR RECIPIENT"
            original_width = c.stringWidth(original_text, "DejaVuSans", 9)
            c.drawString(right_margin - original_width, top_margin - 15, original_text)
            
            if is_first_page:
                # ---------- BUYER DETAILS SECTION ----------
                y -= 5

                # "Buyer (Bill to)" heading with border
                c.setFont("DejaVuSans-Bold", 10)
                c.setFillColor(colors.lightgrey)
                c.rect(left_margin, y - 15, right_margin - left_margin, 18, fill=1, stroke=1)
                c.setFillColor(colors.black)
                c.drawString(left_margin + 5, y - 10, "Buyer (Bill to)")
                y -= 25

                # Buyer information
                c.setFont("DejaVuSans-Bold", 10)
                c.drawString(left_margin, y, f"M/S {transaction.contact.name}")
                y -= 15

                c.setFont("DejaVuSans", 9)
                # Handle None address with text wrapping
                customer_address = transaction.contact.address or "-"
                # Calculate available width for address (leave some margin)
                available_width = right_margin - left_margin - 20
                address_lines = wrap_text(customer_address, available_width, "DejaVuSans", 9)

                for line in address_lines:
                    c.drawString(left_margin, y, line)
                    y -= 13

                # Handle None GSTIN
                customer_gstin = transaction.contact.gstin or "-"
                c.drawString(left_margin, y, f"GSTIN/UIN: {customer_gstin}")
                y -= 13

                # Extract and display buyer state information
                buyer_state_name, buyer_state_code = extract_state_from_gstin(customer_gstin if customer_gstin != "-" else "")
                c.drawString(left_margin, y, f"State Name: {buyer_state_name}, Code: {buyer_state_code}")
                y -= 13

                # Handle None phone
                customer_phone = transaction.contact.phone or "-"
                c.drawString(left_margin, y, f"Phone: {customer_phone}")
                y -= 20

                # ---------- INVOICE INFO ----------
                # Draw these on the right side
                invoice_y = y + 40  # Position relative to buyer details

                c.setFont("DejaVuSans", 9)
                invoice_no = transaction.transaction_number
                invoice_date = format_invoice_date(transaction.transaction_date)
                due_date_obj = calculate_due_date(transaction.transaction_date)
                due_date = format_invoice_date(due_date_obj)

                c.drawString(right_margin - 250, invoice_y, f"Invoice No.: {invoice_no}")
                c.drawString(right_margin - 120, invoice_y, f"Dated: {invoice_date}")
                invoice_y -= 15

                c.drawString(right_margin - 250, invoice_y, f"Due Date: {due_date}")
                
                y -= 20
            
            return y
        
        # Draw first page header
        y = draw_header(c, is_first_page=True)
        
        # ---------- ITEMS TABLE WITH PAGINATION ----------
        # Prepare table header
        table_header = [
            ['Sr.\nNo.', 'SKU / Description', 'HSN / SAC', 'Qty', 'Rate', 
             'IGST\n%', 'IGST\nAmount', 'Total']
        ]
        
        # Total = 515pt (A4 width 595 - 40 left margin - 40 right margin)
        col_widths = [30, 185, 60, 40, 50, 35, 55, 60]
        
        # Calculate totals and prepare items data
        items_data = []
        total_qty = Decimal('0')
        total_taxable = Decimal('0')
        total_igst = Decimal('0')
        
        for item in transaction.items:
            # Calculate: Rate * Quantity = Taxable Value
            # Total = Taxable Value + GST (where GST = Taxable Value * 18%)
            rate_total = item.unit_price * item.quantity
            igst_amount = rate_total * Decimal('0.18')
            total_amount_item = rate_total + igst_amount
            
            # Get display text based on transaction's product_details_display_mode
            display_mode = transaction.product_details_display_mode
            
            if display_mode == ProductDetailsDisplayMode.customer_sku:
                # Try customer-specific SKU first, fallback to company SKU, then product name
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
            
            elif display_mode == ProductDetailsDisplayMode.company_sku:
                # Use company SKU, fallback to product name
                sku_display = item.product.company_sku or item.product.name
            
            elif display_mode == ProductDetailsDisplayMode.product_name:
                # Always use product name
                sku_display = item.product.name
            
            else:
                # Default fallback (should not happen with proper defaults)
                sku_display = item.product.name
            
            items_data.append({
                'name': sku_display,
                'hsn': company_settings.hsn_code,
                'qty': item.quantity,
                'rate': float(item.unit_price),
                'taxable': float(rate_total),  # Keep for summary calculations
                'igst_percent': 18.0,
                'igst_amount': float(igst_amount),
                'total': float(total_amount_item)
            })
            
            total_qty += item.quantity
            total_taxable += rate_total
            total_igst += igst_amount
        
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
                    Paragraph(item['name'], sku_cell_style),
                    item['hsn'],
                    f"{item['qty']:.2f}",
                    f"{item['rate']:.2f}",
                    f"{item['igst_percent']:.2f}",
                    f"{item['igst_amount']:.2f}",
                    f"{item['total']:.2f}"
                ])

            # Add total row only on the last page
            if end_index == len(items_data):
                table_data.append([
                    '',
                    Paragraph('Total', sku_cell_bold_style),
                    '',
                    f"{float(total_qty):.2f}",
                    '',
                    '',
                    f"{float(total_igst):.2f}",
                    f"{float(transaction.total_amount):.2f}"
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
        words = amount_to_words(transaction.total_amount)
        # Wrap long amount in words text
        available_width = right_margin - left_margin - 20
        words_lines = wrap_text(words, available_width, "DejaVuSans", 9)
        for line in words_lines:
            c.drawString(left_margin, y, line)
            y -= 13
        y -= 5  # Extra spacing after wrapped text
        
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
        c.drawString(summary_x + 120, summary_y, f"₹{float(transaction.total_amount):.2f}")
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
