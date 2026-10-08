"""Offline bank-settings and invoice-layout regressions."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table

with patch.dict(os.environ, {
    "TURSO_DATABASE_URL": "libsql://unit-test.invalid",
    "TURSO_AUTH_TOKEN": "not-a-real-token",
    "GCP_BUCKET_NAME": "unit-tests",
    "SECRET_KEY": "unit-test-only",
}):
    from app.main import app as application
    from app.core.db.engine import engine
    from app.modules.pdf_invoices.render import GeneratePdfInvoice, render_invoice
    from app.modules.settings.schemas import CompanyBankDetails, UpdateCompanySettingsDto
    from scripts.pdf_invoice import load_seller


BANK = dict(
    bank_name="Example & Co Bank", bank_account_number="000123456789",
    bank_branch="Central <City>", bank_ifsc="TEST0123456",
)


def seller(**bank):
    return SimpleNamespace(
        company_name="Example Seller", company_address_line1="Market Road",
        company_address_line2="City", company_address_line3="Gujarat",
        seller_gstin="24ABHFM6157G1Z7", seller_phone="Not provided",
        seller_email="billing@example.invalid", hsn_code="-",
        terms_and_conditions="Payment due as agreed.",
        **{**dict.fromkeys(BANK), **bank},
    )


class BankSettingsTests(unittest.TestCase):
    def test_normalizes_strings_and_keeps_leading_zeros(self):
        dto = UpdateCompanySettingsDto(**{**BANK, "bank_ifsc": " test0123456 ", "bank_name": " Example Bank "})
        self.assertEqual(dto.bank_account_number, "000123456789")
        self.assertEqual(dto.bank_ifsc, "TEST0123456")
        self.assertEqual(dto.bank_name, "Example Bank")

    def test_bank_group_can_be_omitted_or_cleared(self):
        self.assertNotIn("bank_name", UpdateCompanySettingsDto(company_name="Seller").model_dump(exclude_unset=True))
        self.assertEqual(
            UpdateCompanySettingsDto(**dict.fromkeys(BANK, " ")).model_dump(exclude_unset=True),
            dict.fromkeys(BANK),
        )
        self.assertIsNone(UpdateCompanySettingsDto(**{**BANK, "bank_branch": None}).bank_branch)

    def test_incomplete_and_malformed_bank_data_rejected(self):
        cases = [
            {"bank_name": "Example Bank"},
            {"bank_branch": None},
            {**BANK, "bank_account_number": None},
            {**BANK, "bank_account_number": 123456},
            {**BANK, "bank_account_number": "123x456"},
            {**BANK, "bank_ifsc": "TEST1123456"},
            {**BANK, "bank_ifsc": "TEST012345"},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                UpdateCompanySettingsDto(**values)
        with self.assertRaises(ValidationError):
            CompanyBankDetails(bank_name="Bank")

    def test_cli_loads_bank_fields_from_company_settings(self):
        session = MagicMock()
        session.execute.return_value.scalar_one.return_value = seller(**BANK)
        with patch("scripts.pdf_invoice.SessionLocal") as sessions, \
                patch.object(engine, "connect", side_effect=AssertionError("Network forbidden")):
            sessions.return_value.__enter__.return_value = session
            result = load_seller()
        for key, value in BANK.items():
            self.assertEqual(getattr(result, key), value)
        session.rollback.assert_called_once()


class BankLayoutTests(unittest.TestCase):
    def render(self, bank, count=1, show_invoice_number=True):
        spec = GeneratePdfInvoice(
            invoice_number="TEST-1", invoice_date="2026-10-06", customer_name="Example Buyer",
            show_invoice_number=show_invoice_number,
            customer_gstin="24AAFCE7955A1ZT", tax_type="cgst_sgst",
            line_items=[dict(name=f"Product {i}", quantity=1, unit_price="100", tax_rate="18") for i in range(count)],
        )
        canvases, bank_positions, bank_text = [], [], []
        original_draw = Table.drawOn

        def make_canvas(*args, **kwargs):
            result = Canvas(*args, **kwargs, pageCompression=0)
            canvases.append(result)
            return result

        def draw(table, canvas, x, y, *args, **kwargs):
            def cell_text(cell):
                if isinstance(cell, (list, tuple)):
                    return "".join(cell_text(part) for part in cell)
                return cell.getPlainText() if hasattr(cell, "getPlainText") else str(cell)

            if cell_text(table._cellvalues[0][0]) == "Company's Bank Details":
                bank_positions.append((canvas.getPageNumber(), y, table._height, canvas._pagesize[1]))
                bank_text.extend(cell_text(cell) for row in table._cellvalues for cell in row)
            return original_draw(table, canvas, x, y, *args, **kwargs)

        with patch.object(engine, "connect", side_effect=AssertionError("Network forbidden")), \
                patch("app.modules.transactions.invoice_generator.canvas.Canvas", side_effect=make_canvas), \
                patch.object(Table, "drawOn", new=draw):
            metadata, content = render_invoice(spec, seller(**bank))
        return metadata, content, bank_positions, canvases[0].getPageNumber() - 1, bank_text

    def test_bank_fields_print_once_without_changing_amounts(self):
        with_bank, content, positions, pages, text = self.render(BANK)
        without_bank, plain, missing, _, _ = self.render({})
        self.assertEqual(with_bank, without_bank)
        for value in ("Example & Co Bank", "000123456789", "Central <City>", "TEST0123456"):
            self.assertEqual(text.count(value), 1)
        self.assertIn(b"000123456789", content)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0][0], pages)
        self.assertEqual(missing, [])
        self.assertNotIn(b"000123456789", plain)

    def test_bank_section_reserves_space_on_final_page(self):
        for count in (1, 22, 30, 60):
            with self.subTest(count=count):
                _, _, positions, pages, _ = self.render(BANK, count)
                self.assertEqual(len(positions), 1)
                page, y, height, page_height = positions[0]
                self.assertEqual(page, pages)
                self.assertGreaterEqual(y, 25 + 82)
                self.assertLessEqual(y + height, page_height - 40)

    def test_invoice_date_remains_without_a_due_date(self):
        for bank in ({}, BANK):
            for numbered in (True, False):
                for count in (1, 30):
                    with self.subTest(bank=bool(bank), numbered=numbered, count=count):
                        _, content, _, _, _ = self.render(bank, count, show_invoice_number=numbered)
                        self.assertIn(b"Dated: 06-Oct-2026", content)
                        self.assertNotIn(b"Due Date", content)
                        self.assertNotIn(b"21-Oct-2026", content)
                        self.assertEqual(b"Invoice No.: TEST-1" in content, numbered)

    def test_long_bank_text_wraps_within_page(self):
        bank = {**BANK, "bank_name": "Example Bank " * 19, "bank_branch": "Central City Branch " * 12}
        _, _, positions, pages, _ = self.render(bank, 30)
        self.assertEqual(len(positions), 1)
        page, y, height, page_height = positions[0]
        self.assertEqual(page, pages)
        self.assertGreaterEqual(y, 107)
        self.assertLessEqual(y + height, page_height - 40)


if __name__ == "__main__":
    unittest.main()
