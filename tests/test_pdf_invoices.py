"""Offline regression cases; no production credentials, cloud or database calls."""
import asyncio
from datetime import date, datetime
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import PreconditionFailed
from pydantic import ValidationError as SchemaError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

with patch.dict(os.environ, {
    "TURSO_DATABASE_URL": "libsql://unit-test.invalid",
    "TURSO_AUTH_TOKEN": "not-a-real-token",
    "GCP_BUCKET_NAME": "unit-tests",
    "SECRET_KEY": "unit-test-only",
}):
    # Load the same model registry as the app, without entering its lifespan.
    from app.main import app as application
    from app.core.db.base import Base
    from app.core.db.engine import engine as configured_engine
    from app.core.exceptions import ConflictError, ExternalServiceError, ValidationError
    from app.core.storage import ImmutableObjectConflictError, StorageService
    from app.modules.pdf_invoices.models import PdfInvoice
    from app.modules.pdf_invoices.render import GeneratePdfInvoice, render_invoice
    from app.modules.pdf_invoices.router import router
    from app.modules.pdf_invoices.schemas import InvoiceLine, PdfInvoiceMetadata, financial_year
    from app.modules.pdf_invoices.service import MAX_PDF_BYTES, PdfInvoiceService, validate_pdf
    from app.modules.transactions.models import Transaction, TransactionType
    from app.modules.transactions.service import TransactionsService
    from app.modules.users.auth import TokenData, get_current_user
    from app.modules.users.models import Role, User
    from scripts import pdf_invoice as cli


PDF = b"%PDF-1.4\nunit-test-fixture\n%%EOF"


def metadata(**overrides):
    values = dict(invoice_number="36", invoice_date="2026-09-24",
                  customer_name="Example Buyer", subtotal="100", igst="18", total_amount="118")
    values.update(overrides)
    return PdfInvoiceMetadata(**values)


class MetadataTests(unittest.TestCase):
    def test_identifiers_and_money_are_canonical_across_database_roundtrip(self):
        original = metadata(invoice_number=" ab/26-27 ", round_off="-0")
        restored = PdfInvoiceMetadata.model_validate({
            **original.model_dump(), "subtotal": Decimal("100.00"), "cgst": Decimal("0.00")
        })
        self.assertEqual(original.invoice_number, "AB/26-27")
        self.assertEqual(original.model_dump_json(), restored.model_dump_json())
        self.assertEqual(original.model_dump(mode="json")["round_off"], "0.00")

    def test_invalid_amounts_identity_and_tax_reconciliation_are_rejected(self):
        cases = [
            {"subtotal": "-1"}, {"subtotal": "NaN"}, {"subtotal": "Infinity"},
            {"subtotal": "100.001"}, {"customer_name": " "}, {"invoice_number": "../36"},
            {"cgst": "1"}, {"total_amount": "119"}, {"source": "generated"},
            {"round_off": "1", "total_amount": "119"},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(SchemaError):
                metadata(**values)

    def test_line_snapshots_reconcile_and_reject_fractional_quantity(self):
        line = dict(name="Folder", quantity=2, unit_price="50", tax_rate="18", hsn_code="39199010")
        result = metadata(source="generated", line_items=[line])
        self.assertEqual(result.line_items[0].unit_price, Decimal("50.00"))
        with self.assertRaises(SchemaError):
            metadata(source="generated", line_items=[{**line, "unit_price": "51"}])
        for quantity in [0, -1, 1.5, True, "2"]:
            with self.subTest(quantity=quantity), self.assertRaises(SchemaError):
                InvoiceLine(**{**line, "quantity": quantity})

    def test_financial_year_changes_on_april_first(self):
        self.assertEqual(financial_year(date(2026, 3, 31)), "2025-2026")
        self.assertEqual(financial_year(date(2026, 4, 1)), "2026-2027")

    def test_pdf_rejects_incomplete_and_oversized_uploads(self):
        self.assertIsNone(validate_pdf(PDF))
        for content in [b"", b"<html>not a PDF</html>", b"%PDF-1.4\ntruncated", b"x" * (MAX_PDF_BYTES + 1)]:
            with self.subTest(length=len(content)), self.assertRaises(ValidationError):
                validate_pdf(content)

    @patch("app.modules.pdf_invoices.render.InvoiceGenerator.generate_invoice_pdf", return_value=PDF)
    def test_render_uses_snapshots_and_exact_inclusive_target(self, renderer):
        spec = GeneratePdfInvoice(
            invoice_number="36", invoice_date="2026-09-24", customer_name="Buyer",
            tax_type="igst", total_amount="10000",
            line_items=[
                {"name": '3" A & B', "quantity": 1413, "unit_price": "2", "tax_rate": "18"},
                {"name": '2.5" x 12"', "quantity": 1412, "unit_price": "4", "tax_rate": "18"},
            ],
        )
        result, content = render_invoice(spec, SimpleNamespace())
        self.assertEqual((result.subtotal, result.igst, result.round_off, result.total_amount),
                         (Decimal("8474"), Decimal("1525.32"), Decimal("0.68"), Decimal("10000")))
        self.assertEqual(content, PDF)
        self.assertEqual(renderer.call_args.args[0].items[0].product.name, '3" A &amp; B')
        self.assertIsNone(renderer.call_args.args[2])

    @patch("app.modules.pdf_invoices.render.InvoiceGenerator.generate_invoice_pdf", return_value=PDF)
    def test_intra_state_split_matches_per_rate_buckets_and_round_up(self, renderer):
        spec = GeneratePdfInvoice(
            invoice_number="40", invoice_date="2026-09-24", customer_name="Buyer", tax_type="cgst_sgst",
            line_items=[
                {"name": "A", "quantity": 1, "unit_price": "0.20", "tax_rate": "5"},
                {"name": "B", "quantity": 1, "unit_price": "0.10", "tax_rate": "12"},
            ],
        )
        result, _ = render_invoice(spec, SimpleNamespace())
        self.assertEqual((result.cgst, result.sgst, result.igst),
                         (Decimal("0.00"), Decimal("0.02"), Decimal("0.00")))
        self.assertEqual((result.total_amount, result.round_off), (Decimal("1.00"), Decimal("0.68")))


class RegisterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        network_guard = patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden"))
        network_guard.start()
        self.addCleanup(network_guard.stop)
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(User(id=1, username="staff", password="unused", name="Staff", role=Role.STAFF))
            db.commit()

        async def local_db(fn):
            with Session(self.engine, expire_on_commit=False) as db:
                result = fn(db)
                db.commit()
                return result

        self.local_db = local_db
        db_patch = patch("app.modules.pdf_invoices.service.run_db", side_effect=local_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)
        upload_patch = patch.object(StorageService, "upload_file", return_value=("unused", "unused"))
        self.upload = upload_patch.start()
        self.addCleanup(upload_patch.stop)

    async def register(self, values=None, pdf=PDF):
        return await asyncio.wait_for(PdfInvoiceService.register(values or metadata(), pdf, "bill.pdf", 1), 3)

    async def test_register_is_durable_and_idempotent_without_accounting_writes(self):
        first = await self.register()
        second = await self.register(metadata(subtotal="100.00", cgst="0.00"))
        self.assertEqual((first.id, first.upload_status), (second.id, "ready"))
        self.upload.assert_called_once()
        self.assertTrue(self.upload.call_args.kwargs["immutable"])
        self.assertIn("/standalone/2026-2027/", self.upload.call_args.args[1])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PdfInvoice)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 0)
            for table in ("contacts", "payments", "inventory_log", "container_product", "product"):
                self.assertEqual(db.scalar(select(func.count()).select_from(Base.metadata.tables[table])), 0)

    async def test_existing_transaction_number_or_pdf_checksum_cannot_be_imported(self):
        with Session(self.engine) as db:
            db.execute(Transaction.__table__.insert().values(
                transaction_number="36", transaction_date=date(2026, 9, 24), type=TransactionType.sale,
                contact_id=1, subtotal=100, total_amount=118, invoice_checksum=hashlib.md5(PDF).hexdigest(),
            ))
            db.commit()
        for values, content in [
            (metadata(), b"%PDF-1.4\nrenamed copy\n%%EOF"),
            (metadata(invoice_number="37"), PDF),
        ]:
            with self.subTest(number=values.invoice_number), self.assertRaises(ConflictError):
                await self.register(values, content)
        self.upload.assert_not_called()

    async def test_existing_pdf_or_number_with_different_details_conflicts(self):
        await self.register()
        for values, content in [
            (metadata(notes="different"), PDF),
            (metadata(invoice_number="37"), PDF),
            (metadata(), b"%PDF-1.4\nother\n%%EOF"),
        ]:
            with self.subTest(values=values.invoice_number), self.assertRaises(ConflictError):
                await self.register(values, content)

    async def test_cloud_failure_preserves_pending_row_and_retry_finishes_same_id(self):
        self.upload.side_effect = OSError("cloud unavailable")
        with self.assertRaises(ExternalServiceError):
            await self.register()
        pending = await PdfInvoiceService.list_invoices(1, 25, None, None, None)
        self.assertEqual(pending.items[0].upload_status, "pending")
        with self.assertRaises(ConflictError):
            await PdfInvoiceService.download(pending.items[0].id)
        self.upload.side_effect = None
        result = await self.register()
        self.assertEqual(result.id, pending.items[0].id)
        self.assertEqual(result.upload_status, "ready")

    async def test_cloud_success_then_db_failure_reuses_original_object(self):
        calls = 0

        async def interrupted(fn):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("DB final commit unavailable")
            return await self.local_db(fn)

        with patch("app.modules.pdf_invoices.service.run_db", side_effect=interrupted):
            with self.assertRaises(OSError):
                await self.register()
        result = await self.register()
        self.assertEqual(result.upload_status, "ready")
        self.assertEqual(self.upload.call_args_list[0], self.upload.call_args_list[1])

    async def test_turso_unique_race_retries_but_unrelated_value_error_propagates(self):
        existing = await self.register()
        for message, expected_retry in [
            ("Hrana: UNIQUE constraint failed: pdf_invoices.pdf_sha256", True),
            ("database value conversion failed", False),
        ]:
            with self.subTest(message=message):
                with patch("app.modules.pdf_invoices.service.run_db",
                           side_effect=[ValueError(message), existing]) as execute:
                    if expected_retry:
                        self.assertEqual((await self.register()).id, existing.id)
                        self.assertEqual(execute.await_count, 2)
                    else:
                        with self.assertRaisesRegex(ValueError, "conversion"):
                            await self.register()
                        self.assertEqual(execute.await_count, 1)

    async def test_list_filter_pagination_and_download_integrity(self):
        first = await self.register()
        await self.register(metadata(invoice_number="37", invoice_date="2026-09-25", customer_name="Other"),
                            b"%PDF-1.4\nsecond\n%%EOF")
        page = await PdfInvoiceService.list_invoices(1, 1, None, None, None)
        self.assertEqual((page.total, page.has_more, page.items[0].invoice_number), (2, True, "37"))
        found = await PdfInvoiceService.list_invoices(1, 25, "Example", date(2026, 9, 24), date(2026, 9, 24))
        self.assertEqual([row.id for row in found.items], [first.id])
        with self.assertRaises(ValidationError):
            await PdfInvoiceService.list_invoices(1, 25, None, date(2026, 10, 1), date(2026, 9, 1))
        with patch.object(StorageService, "download_file", return_value=PDF):
            self.assertEqual(await PdfInvoiceService.download(first.id), (PDF, "36.pdf"))
        with patch.object(StorageService, "download_file", return_value=b"wrong"):
            with self.assertRaises(ConflictError):
                await PdfInvoiceService.download(first.id)

    async def test_list_orders_by_date_added_with_stable_pagination_and_invoice_date_filters(self):
        first = await self.register(metadata(invoice_date="2026-09-25"))
        second = await self.register(metadata(invoice_number="37", invoice_date="2026-09-24"),
                                     b"%PDF-1.4\nsecond\n%%EOF")
        third = await self.register(metadata(invoice_number="38", invoice_date="2026-10-08"),
                                    b"%PDF-1.4\nthird\n%%EOF")
        with Session(self.engine) as db:
            db.get(PdfInvoice, first.id).created_at = datetime(2026, 10, 8, 10)
            db.get(PdfInvoice, second.id).created_at = datetime(2026, 10, 8, 10)
            db.get(PdfInvoice, third.id).created_at = datetime(2026, 10, 7, 10)
            db.get(PdfInvoice, third.id).updated_at = datetime(2026, 10, 9, 10)
            db.commit()

        page = await PdfInvoiceService.list_invoices(1, 2, None, None, None)
        self.assertEqual([row.id for row in page.items], [second.id, first.id])
        self.assertEqual((page.total, page.has_more), (3, True))
        next_page = await PdfInvoiceService.list_invoices(2, 2, None, None, None)
        self.assertEqual([row.id for row in next_page.items], [third.id])
        self.assertEqual((next_page.total, next_page.has_more), (3, False))

        filtered = await PdfInvoiceService.list_invoices(
            1, 25, "Example", date(2026, 9, 24), date(2026, 9, 25)
        )
        self.assertEqual([row.id for row in filtered.items], [second.id, first.id])
        self.assertEqual((filtered.total, filtered.has_more), (2, False))

    async def test_sale_number_skips_pending_and_ready_pdf_reservations(self):
        self.upload.side_effect = OSError("cloud unavailable")
        with self.assertRaises(ExternalServiceError):
            await self.register(metadata(invoice_number="SALE-0001"))
        self.upload.side_effect = None
        await self.register(metadata(invoice_number="SALE-0002"), b"%PDF-1.4\nsecond sale\n%%EOF")
        with Session(self.engine) as db:
            self.assertEqual(TransactionsService._generate_transaction_number(db, TransactionType.sale), "SALE-0003")
            self.assertEqual(TransactionsService._generate_transaction_number(db, TransactionType.purchase), "PUR-0001")


class UploadAndCliTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def test_authenticated_readers_cannot_all_upload(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            self.assertIn(client.get("/pdf-invoices").status_code, [401, 403])
            for role, expected in [("JOBBER", 403), ("MANAGER", 403), ("STAFF", 201), ("ADMIN", 201)]:
                with self.subTest(role=role):
                    app.dependency_overrides[get_current_user] = lambda: TokenData(1, "staff", role)
                    result = {
                        **metadata().model_dump(mode="json"), "id": 1, "financial_year": "2026-2027",
                        "original_filename": "bill.pdf", "pdf_sha256": hashlib.sha256(PDF).hexdigest(),
                        "upload_status": "ready", "created_at": "2026-09-24T00:00:00", "created_by_id": 1,
                    }
                    with patch.object(PdfInvoiceService, "register", new_callable=AsyncMock, return_value=result) as register:
                        response = client.post("/pdf-invoices", data={"metadata": metadata().model_dump_json()},
                                               files={"file": ("bill.pdf", PDF, "application/pdf")})
                        self.assertEqual(response.status_code, expected)
                        self.assertEqual(register.await_count, 1 if expected == 201 else 0)

    def test_immutable_storage_accepts_only_identical_existing_object(self):
        blob = Mock()
        blob.upload_from_string.side_effect = PreconditionFailed("object exists")
        bucket = Mock()
        bucket.blob.return_value = blob
        with patch.object(StorageService, "_get_bucket", return_value=bucket):
            blob.download_as_bytes.return_value = PDF
            _, checksum = StorageService.upload_file(PDF, "invoices/standalone/test.pdf", immutable=True)
            self.assertEqual(checksum, hashlib.md5(PDF).hexdigest())
            self.assertEqual(blob.upload_from_string.call_args.kwargs["if_generation_match"], 0)
            blob.download_as_bytes.return_value = b"different"
            with self.assertRaises(ImmutableObjectConflictError):
                StorageService.upload_file(PDF, "invoices/standalone/test.pdf", immutable=True)

    def test_generate_failure_retains_exact_pdf_and_metadata_for_retry(self):
        spec = GeneratePdfInvoice(
            invoice_number="36", invoice_date="2026-09-24", customer_name="Buyer", tax_type="igst",
            line_items=[{"name": "Folder", "quantity": 1, "unit_price": "100", "tax_rate": "18"}],
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bill.pdf"
            with patch.object(cli, "api_config"), patch.object(cli, "load_seller"), \
                    patch.object(cli, "render_invoice", return_value=(metadata(), PDF)), \
                    patch.object(cli, "register_pdf", side_effect=RuntimeError("upload failed")):
                with self.assertRaisesRegex(RuntimeError, "upload failed"):
                    cli.generate(spec, output)
                self.assertEqual(output.read_bytes(), PDF)
                self.assertEqual(PdfInvoiceMetadata.model_validate_json(
                    output.with_suffix(".metadata.json").read_text()).model_dump(), metadata().model_dump())
                with self.assertRaises(FileExistsError):
                    cli.generate(spec, output)

    def test_cli_verifies_cloud_bytes_before_writing_registration_receipt(self):
        record = {
            **metadata().model_dump(mode="json"), "id": 1, "financial_year": "2026-2027",
            "original_filename": "bill.pdf", "pdf_sha256": hashlib.sha256(PDF).hexdigest(),
            "upload_status": "ready", "created_at": "2026-09-24T00:00:00", "created_by_id": 1,
        }
        response = Mock(status_code=201)
        response.json.return_value = {"success": True, "data": record}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli, "api_config", return_value=("https://unit-test.invalid/api", "test-token")), \
                patch.object(cli.requests, "post", return_value=response), \
                patch.object(cli.requests, "get", return_value=Mock(status_code=200, content=b"wrong")) as download, \
                patch("builtins.print") as output:
            path = Path(directory) / "bill.pdf"
            path.write_bytes(PDF)
            with self.assertRaisesRegex(RuntimeError, "read-back"):
                cli.register_pdf(metadata(), path)
            self.assertFalse(path.with_suffix(".registered.json").exists())
            output.assert_not_called()
            download.return_value.content = PDF
            self.assertEqual(cli.register_pdf(metadata(), path), record)
            self.assertEqual(cli.json.loads(path.with_suffix(".registered.json").read_text()), record)


if __name__ == "__main__":
    unittest.main()
