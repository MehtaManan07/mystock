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
from xml.sax.saxutils import escape


from app.modules.transactions.models import Transaction, ProductDetailsDisplayMode, TaxType
from app.modules.settings.models import CompanySettings
from app.modules.settings.schemas import CompanyBankDetails
from app.modules.vendor_product_skus.models import VendorProductSku
from app.modules.products.models import Product
from app.core.utils import amount_to_words, format_invoice_date
from sqlalchemy.orm import Session
from sqlalchemy import and_


class InvoiceGenerator:
    """
    PDF Invoice Generator using ReportLab.
    Generates professional GST-compliant invoices with automatic pagination.
    """

    @staticmethod
    def _format_amount(value) -> str:
        """Format a number in Indian digit grouping, e.g. 1,04,152.34."""
        negative = float(value) < 0
        whole, _, fraction = f"{abs(float(value)):.2f}".partition('.')

        if len(whole) > 3:
            head, tail = whole[:-3], whole[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            whole = ','.join(groups + [tail])

        return f"{'-' if negative else ''}{whole}.{fraction}"

    @staticmethod
    def generate_invoice_pdf(
        transaction: Transaction,
        company_settings: CompanySettings,
        db: Session,
        *,
        show_invoice_number: bool = True,
    ) -> bytes:
        """
        Generate a professional GST invoice PDF from transaction data.
        
        Args:
            transaction: Transaction model with items, contact, etc.
            company_settings: Company settings with seller information
            db: Database session for vendor SKU lookups
            show_invoice_number: Print the invoice number; enabled for normal invoices.
            
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

            # Company address (up to 3 lines, 9pt). Placeholder values such as
            # '0' or '-' are skipped so they never show up on the invoice.
            c.setFont("DejaVuSans", 9)
            address_lines = [
                company_settings.company_address_line1,
                company_settings.company_address_line2,
                company_settings.company_address_line3,
            ]
            for address_line in address_lines:
                if not address_line or address_line.strip() in ('', '0', '-'):
                    continue
                c.drawString(left_margin, y, address_line.strip())
                y -= 12
            y -= 6

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
            y -= 18

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
                y -= 16

                # ---------- INVOICE INFO ----------
                # Draw these on the right side
                invoice_y = y + 40  # Position relative to buyer details

                c.setFont("DejaVuSans", 9)
                invoice_no = transaction.transaction_number
                invoice_date = format_invoice_date(transaction.transaction_date)

                if show_invoice_number:
                    c.drawString(right_margin - 250, invoice_y, f"Invoice No.: {invoice_no}")
                c.drawRightString(right_margin, invoice_y, f"Dated: {invoice_date}")

                y -= 12
            
            return y
        
        # Draw first page header
        y = draw_header(c, is_first_page=True)
        
        # ---------- ITEMS TABLE WITH PAGINATION ----------
        # Determine tax type for summary section
        is_intra_state = transaction.tax_type == TaxType.cgst_sgst

        # Table header — per-line GST %, with the rate-wise breakup in the summary
        table_header = [
            ['Sr.\nNo.', 'SKU / Description', 'HSN / SAC', 'Qty', 'Rate', 'GST %', 'Total']
        ]
        # Total = 515pt (A4 width 595 - 40 left margin - 40 right margin)
        col_widths = [30, 200, 65, 40, 50, 45, 85]
        
        # Calculate totals and prepare items data
        items_data = []
        total_qty = Decimal('0')
        total_taxable = Decimal('0')
        total_tax = Decimal('0')

        # Tax is charged per line at that line's own rate. Rate-wise buckets drive
        # the summary so a mixed-slab invoice (e.g. some 18%, some 5%) reports each
        # slab separately instead of a meaningless average.
        subtotal = transaction.subtotal or Decimal('0')

        # Legacy fallback for invoices issued before per-item tax existed: those
        # rows have no tax_rate, so derive the single blended rate as before.
        legacy_rate = (
            (transaction.tax_amount / subtotal * Decimal('100'))
            if subtotal > 0 else Decimal('0')
        )

        # Taxable value and tax accumulated per distinct rate, in first-seen order
        rate_buckets: dict = {}

        # Batch-fetch vendor SKUs for all items in 1 query instead of N
        display_mode = transaction.product_details_display_mode
        vendor_sku_map: dict = {}
        if display_mode == ProductDetailsDisplayMode.customer_sku:
            item_product_ids = [item.product_id for item in transaction.items]
            vendor_skus = db.query(VendorProductSku).filter(
                and_(
                    VendorProductSku.product_id.in_(item_product_ids),
                    VendorProductSku.vendor_id == transaction.contact_id,
                    VendorProductSku.deleted_at.is_(None),
                )
            ).all()
            vendor_sku_map = {vs.product_id: vs.vendor_sku for vs in vendor_skus}

        for item in transaction.items:
            # Calculate: Rate * Quantity = Taxable Value
            rate_total = item.unit_price * item.quantity

            # Prefer the rate/amount frozen on the line at sale time. Fall back to
            # the invoice-wide blended rate only for legacy rows that predate it.
            if item.tax_rate is not None:
                item_rate = item.tax_rate
            else:
                item_rate = legacy_rate

            if item.tax_amount is not None:
                tax_amount_item = item.tax_amount
            else:
                tax_amount_item = (rate_total * item_rate / Decimal('100')).quantize(Decimal('0.01'))

            total_amount_item = rate_total + tax_amount_item

            # Get display text based on transaction's product_details_display_mode
            if display_mode == ProductDetailsDisplayMode.customer_sku:
                # Use batch-fetched vendor SKU, fallback to company SKU, then product name
                sku_display = vendor_sku_map.get(item.product_id) or item.product.company_sku or item.product.name

            elif display_mode == ProductDetailsDisplayMode.company_sku:
                # Use company SKU, fallback to product name
                sku_display = item.product.company_sku or item.product.name
            
            elif display_mode == ProductDetailsDisplayMode.product_name:
                # Always use product name
                sku_display = item.product.name
            
            else:
                # Default fallback (should not happen with proper defaults)
                sku_display = item.product.name

            bucket = rate_buckets.setdefault(
                item_rate, {'taxable': Decimal('0'), 'tax': Decimal('0')}
            )
            bucket['taxable'] += rate_total
            bucket['tax'] += tax_amount_item

            items_data.append({
                'name': sku_display,
                'hsn': item.product.hsn_code or company_settings.hsn_code,
                'qty': item.quantity,
                'rate': float(item.unit_price),
                'taxable': float(rate_total),
                'tax_percent': float(item_rate),
                'tax_amount': float(tax_amount_item),
                'total': float(total_amount_item)
            })

            total_qty += item.quantity
            total_taxable += rate_total
            total_tax += tax_amount_item

        # ---------- FOOTER GEOMETRY (computed before paging) ----------
        # The paging loop needs to know how tall the footer is so the last page
        # can reserve room for it instead of guessing a row count.
        summary_width = 220
        summary_x = right_margin - summary_width
        summary_pad = 8
        line_height = 13

        # Rate lines to print: one CGST+SGST pair (or one IGST line) per distinct rate
        summary_rates = [
            r for r in sorted(rate_buckets, reverse=True)
            if not (rate_buckets[r]['tax'] == 0 and r == 0)
        ]

        # Round off keeps the summary self-consistent: taxable + tax + round off
        # equals the total actually charged.
        discount = transaction.discount_amount or Decimal('0')
        round_off = transaction.total_amount - (total_taxable + total_tax - discount)

        # Build the rows first so the enclosing box can be sized exactly.
        summary_rows = [("Taxable Amount", InvoiceGenerator._format_amount(total_taxable), False)]
        for item_rate in summary_rates:
            bucket = rate_buckets[item_rate]
            if is_intra_state:
                half_percent = float(item_rate) / 2
                cgst_amount = (bucket['tax'] / Decimal('2')).quantize(Decimal('0.01'))
                # Give any odd paisa to SGST so the two halves sum to the line tax
                sgst_amount = bucket['tax'] - cgst_amount
                summary_rows.append((f"Add : CGST @ {half_percent:.2f}%", InvoiceGenerator._format_amount(cgst_amount), False))
                summary_rows.append((f"Add : SGST @ {half_percent:.2f}%", InvoiceGenerator._format_amount(sgst_amount), False))
            else:
                summary_rows.append((f"Add : IGST @ {float(item_rate):.2f}%", InvoiceGenerator._format_amount(bucket['tax']), False))

        if discount:
            summary_rows.append(("Less : Discount", InvoiceGenerator._format_amount(discount), False))

        summary_rows.append(("Total Tax", InvoiceGenerator._format_amount(total_tax), False))

        if round_off != 0:
            summary_rows.append(("Round Off", f"{'+' if round_off > 0 else '-'}{InvoiceGenerator._format_amount(abs(round_off))}", False))

        summary_rows.append(("Total Amount", f"\u20b9{InvoiceGenerator._format_amount(transaction.total_amount)}", True))

        box_height = len(summary_rows) * line_height + summary_pad

        # Left column height: "Total in words" + wrapped words + terms heading + terms
        left_width = summary_x - left_margin - 20
        words_lines = wrap_text(amount_to_words(transaction.total_amount), left_width, "DejaVuSans", 9)
        terms_lines = []
        for term in (company_settings.terms_and_conditions or '').split('\n'):
            if term.strip():
                terms_lines.extend(wrap_text(term.strip(), left_width, "DejaVuSans", 8))
        left_col_height = 15 + len(words_lines) * 13 + 8 + 14 + len(terms_lines) * 12

        bank = CompanyBankDetails.model_validate(company_settings, from_attributes=True)
        bank_table = None
        bank_height = 0
        if bank.bank_name:
            assert bank.bank_account_number and bank.bank_ifsc
            bank_rows = [
                [Paragraph("Company's Bank Details", sku_cell_bold_style), ""],
                ["Bank Name", Paragraph(escape(bank.bank_name), sku_cell_style)],
                ["A/c No.", Paragraph(escape(bank.bank_account_number), sku_cell_style)],
            ]
            if bank.bank_branch:
                bank_rows.append(["Branch / Code", Paragraph(escape(bank.bank_branch), sku_cell_style)])
            bank_rows.append(["IFSC", Paragraph(escape(bank.bank_ifsc), sku_cell_style)])
            bank_table = Table(bank_rows, colWidths=[110, right_margin - left_margin - 110])
            bank_table.setStyle(TableStyle([
                ('SPAN', (0, 0), (-1, 0)),
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            _, bank_height = bank_table.wrapOn(c, width, height)

        # Signature block below the two columns: gap + "Certified" + "For <company>"
        # + "Authorised Signatory", which must stay clear of the page edge.
        signature_height = 22 + 26 + 34
        page_bottom_clear = 25
        footer_height = max(box_height + 12, left_col_height) + signature_height
        if bank_table is not None:
            footer_height += 12 + bank_height

        # ---------- ITEMS TABLE (paged by measurement) ----------
        def build_items_table(start, end, with_total_row):
            """Build the items table for [start, end) and measure it."""
            table_data = table_header.copy()
            for idx in range(start, end):
                row_item = items_data[idx]
                table_data.append([
                    str(idx + 1),
                    Paragraph(row_item['name'], sku_cell_style),
                    row_item['hsn'],
                    f"{row_item['qty']:.2f}",
                    InvoiceGenerator._format_amount(row_item['rate']),
                    f"{row_item['tax_percent']:.2f}%",
                    InvoiceGenerator._format_amount(row_item['total'])
                ])
            if with_total_row:
                table_data.append([
                    '',
                    Paragraph('Total', sku_cell_bold_style),
                    '',
                    f"{float(total_qty):.2f}",
                    '',
                    '',
                    InvoiceGenerator._format_amount(total_taxable + total_tax)
                ])

            style = [
                ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
                ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
                ('RIGHTPADDING', (4, 1), (4, -1), 6),
                ('RIGHTPADDING', (6, 1), (6, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]
            # Only the grand-total row is bold - never a page's last item row.
            if with_total_row:
                style.append(('FONTNAME', (0, -1), (-1, -1), 'DejaVuSans-Bold'))

            built = Table(table_data, colWidths=col_widths)
            built.setStyle(TableStyle(style))
            _, measured_height = built.wrapOn(c, width, height)
            return built, measured_height

        item_index = 0
        page_number = 1

        while item_index < len(items_data):
            if page_number > 1:
                c.showPage()
                y = draw_header(c, is_first_page=False)

            available = y - bottom_margin
            remaining = len(items_data) - item_index

            # Best case: everything left, plus the total row and the footer, fits here.
            # The footer is measured against the page edge, not bottom_margin, since
            # bottom_margin already exists to reserve that same footer space.
            table, table_height = build_items_table(item_index, len(items_data), True)
            if table_height + 14 + footer_height <= y - page_bottom_clear:
                table.drawOn(c, left_margin, y - table_height)
                y = y - table_height - 14
                break

            # Otherwise pack as many item rows onto this page as physically fit.
            rows_that_fit = 0
            for count in range(1, remaining + 1):
                _, probe_height = build_items_table(item_index, item_index + count, False)
                if probe_height > available:
                    break
                rows_that_fit = count

            # If every remaining row plus the grand-total row still fits here, keep
            # them together on this page and let the footer flow onto the next one.
            # Only the footer is too tall to fit; orphaning a row as well would
            # strand a single line above the totals on an otherwise empty page.
            if rows_that_fit == remaining:
                whole, whole_height = build_items_table(item_index, len(items_data), True)
                if whole_height <= available:
                    whole.drawOn(c, left_margin, y - whole_height)
                    y = y - whole_height - 14
                    break

            # Guarantee forward progress, and always leave at least one row to
            # carry the total row and footer onto the next page.
            rows_that_fit = max(1, min(rows_that_fit, remaining - 1))

            table, table_height = build_items_table(item_index, item_index + rows_that_fit, False)
            table.drawOn(c, left_margin, y - table_height)
            y = y - table_height - 14

            item_index += rows_that_fit
            page_number += 1

        # ---------- TOTALS SUMMARY (right) AND WORDS / TERMS (left) ----------
        # Both columns hang off the bottom of the items table and flow downward,
        # so a mixed-rate invoice with many slabs can never overlap the table.
        # The items table may have used the whole page, so give the footer its own
        # page rather than letting the totals box run off the bottom edge.
        if y - footer_height < page_bottom_clear:
            c.showPage()
            y = draw_header(c, is_first_page=False)

        content_top = y
        box_top = content_top
        box_bottom = box_top - box_height

        # Outer box + a separating rule above the grand total
        c.setLineWidth(0.5)
        c.rect(summary_x, box_bottom, summary_width, box_height)

        label_x = summary_x + summary_pad
        value_x = right_margin - summary_pad
        row_y = box_top - summary_pad - 4

        for label, value, is_grand_total in summary_rows:
            if is_grand_total:
                rule_y = row_y + line_height - 5
                c.line(summary_x, rule_y, right_margin, rule_y)
                c.setFont("DejaVuSans-Bold", 10)
            else:
                c.setFont("DejaVuSans", 9)
            c.drawString(label_x, row_y, label)
            c.drawRightString(value_x, row_y, value)
            row_y -= line_height

        summary_bottom = box_bottom
        c.setFont("DejaVuSans-Oblique", 8)
        summary_bottom -= 12
        c.drawRightString(value_x, summary_bottom, "(E & O.E.)")

        # ---------- AMOUNT IN WORDS (left column) ----------
        left_y = content_top

        c.setFont("DejaVuSans-Bold", 9)
        c.drawString(left_margin, left_y, "Total in words")
        left_y -= 15

        c.setFont("DejaVuSans", 9)
        for line in words_lines:
            c.drawString(left_margin, left_y, line)
            left_y -= 13
        left_y -= 8

        # ---------- TERMS AND CONDITIONS (left column) ----------
        c.setFont("DejaVuSans-Bold", 9)
        c.drawString(left_margin, left_y, "Terms and Conditions")
        left_y -= 14

        c.setFont("DejaVuSans", 8)
        for line in terms_lines:
            c.drawString(left_margin, left_y, line)
            left_y -= 12

        y = min(left_y, summary_bottom)
        if bank_table is not None:
            y -= 12 + bank_height
            bank_table.drawOn(c, left_margin, y)

        # ---------- FOOTER ----------
        y -= 22

        # The signature block below needs 60pt and must keep ~25pt clear of the
        # page edge; overflow to a fresh page rather than running off it.
        if y - 60 < 25:
            c.showPage()
            y = draw_header(c, is_first_page=False)

        c.setFont("DejaVuSans", 8)
        c.drawString(left_margin, y, "Certified that the particulars given above are true and correct.")
        y -= 26

        c.setFont("DejaVuSans-Bold", 9)
        c.drawRightString(right_margin, y, f"For {company_settings.company_name}")
        y -= 34

        c.setFont("DejaVuSans", 8)
        c.drawRightString(right_margin, y, "Authorised Signatory")
        
        # Save PDF
        c.save()
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
