"""Shared number and filename regressions; all DB/storage/HTTP work is offline."""
import asyncio
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import requests
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

with patch.dict(os.environ, {
    "POSTGRES_URL": "postgresql+psycopg://localhost:5432/unit-test-invalid",
    "GCP_BUCKET_NAME": "unit-tests",
    "SECRET_KEY": "unit-test-only",
}):
    from app.main import app as application
    from app.core.db.base import Base
    from app.core.db.engine import engine as configured_engine
    from app.core.exceptions import ConflictError, NotFoundError, ValidationError
    from app.core.invoice_filenames import invoice_filename
    from app.core.invoice_numbers import lock_sales_numbering, next_sale_number
    from app.core.storage import StorageService
    from app.modules.contacts.models import Contact
    from app.modules.pdf_invoices.models import PdfInvoice, PdfInvoiceNumberReservation
    from app.modules.pdf_invoices.render import GeneratePdfInvoice
    from app.modules.pdf_invoices.router import router
    from app.modules.pdf_invoices.schemas import (
        PdfInvoiceMetadata, PdfInvoiceNumberResponse, PdfInvoiceResponse, ReservePdfInvoiceNumber,
    )
    from app.modules.pdf_invoices.service import PdfInvoiceService
    from app.modules.transactions.invoice_service import InvoiceService
    from app.modules.transactions.models import Transaction, TransactionType
    from app.modules.transactions.service import TransactionsService
    from app.modules.users.auth import TokenData, get_current_user
    from app.modules.users.models import User
    from scripts import pdf_invoice as cli


PDF = b"%PDF-1.4\nnumbering-fixture\n%%EOF"
DAY = date(2026, 10, 21)


class FilenameTests(unittest.TestCase):
    def test_filename_preserves_invoice_identity_and_normalizes_customer(self):
        for number, name, expected in (
            ("46", "AZAD IMITATION", "46_AZAD-IMITATION_2026-10-21.pdf"),
            ("SALE-0046", "AZAD IMITATION", "SALE-0046_AZAD-IMITATION_2026-10-21.pdf"),
            ("29/26-27", "  A & B / Traders  ", "29%2F26-27_A-B-TRADERS_2026-10-21.pdf"),
            ("29-26-27", "  A & B / Traders  ", "29-26-27_A-B-TRADERS_2026-10-21.pdf"),
            ("SALE-0064", "Café", "SALE-0064_CAFE_2026-10-21.pdf"),
            ("SALE-0064", "商店", "SALE-0064_CUSTOMER_2026-10-21.pdf"),
        ):
            with self.subTest(number=number, name=name):
                self.assertEqual(invoice_filename(number, name, DAY), expected)

    def test_filename_is_bounded_and_cannot_introduce_directories_or_headers(self):
        filename = invoice_filename("A" + "/" * 49, 'X' * 255 + '"/\r\nbad', DAY)
        self.assertEqual(filename, "A" + "%2F" * 49 + "_" + "X" * 80 + "_2026-10-21.pdf")
        self.assertLessEqual(len(filename.encode()), 255)

    def test_postgres_numbering_lock_is_transaction_scoped(self):
        db = Mock()
        db.get_bind.return_value.dialect.name = "postgresql"
        lock_sales_numbering(db)
        self.assertEqual(str(db.execute.call_args.args[0]), "SELECT pg_advisory_xact_lock(1262698830)")


class NumberingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        guard = patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                Contact(id=1, name="Example Buyer", phone="Not provided", type="customer"),
                Contact(id=2, name="Other Buyer", phone="Not provided", type="customer"),
                User(id=1, username="staff", password="unused", name="Staff", role="STAFF"),
            ])
            db.commit()

        async def local_db(fn):
            with Session(self.engine, expire_on_commit=False) as db:
                result = fn(db)
                db.commit()
                return result

        for module in ("pdf_invoices.service", "transactions.invoice_service"):
            patched = patch(f"app.modules.{module}.run_db", side_effect=local_db)
            patched.start()
            self.addCleanup(patched.stop)

    def request(self, **changes):
        return ReservePdfInvoiceNumber(**{
            "request_id": uuid4(), "customer_id": 1, "spec_sha256": "a" * 64, **changes,
        })

    async def reserve(self, request=None, user=1):
        return await asyncio.wait_for(PdfInvoiceService.reserve_number(request or self.request(), user), 3)

    def transaction(self, number, **changes):
        with Session(self.engine) as db:
            db.execute(Transaction.__table__.insert().values(
                transaction_number=number, transaction_date=DAY, contact_id=1,
                type="sale", subtotal=100, total_amount=118, **changes,
            ))
            db.commit()

    async def test_pdf_and_transaction_numbers_share_highest_value_including_retired_rows(self):
        self.transaction("SALE-0010", deleted_at=datetime(2026, 10, 21))
        self.transaction("SALE-0002")
        with Session(self.engine) as db:
            values = PdfInvoiceMetadata(
                invoice_number="SALE-0020", invoice_date=DAY, customer_id=1, customer_name="Example Buyer",
                subtotal=100, igst=18, total_amount=118,
            )
            row = PdfInvoiceService._reserve(db, values, PDF, "old.pdf", 1)
            row.deleted_at = datetime(2026, 10, 21)
            db.commit()
        reserved = await self.reserve()
        self.assertEqual(reserved.invoice_number, "SALE-0021")
        with Session(self.engine) as db:
            self.assertEqual(TransactionsService._generate_transaction_number(db, TransactionType.sale), "SALE-0022")
            self.assertEqual(TransactionsService._generate_transaction_number(db, TransactionType.purchase), "PUR-0001")
            self.assertEqual(db.scalar(select(PdfInvoice.invoice_number)), "SALE-0020")
            self.assertEqual(db.get(Contact, 1).balance, 0)

    async def test_same_request_retries_the_same_number_without_issuing_a_bill(self):
        request = self.request()
        first = await self.reserve(request)
        self.assertEqual(await self.reserve(request), first)
        self.assertEqual((await self.reserve()).invoice_number, "SALE-0002")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PdfInvoiceNumberReservation)), 2)
            self.assertEqual(db.scalar(select(func.count()).select_from(PdfInvoice)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 0)
            self.assertEqual(next_sale_number(db), "SALE-0003")

    async def test_reusing_request_for_another_payload_customer_or_user_is_rejected(self):
        request = self.request()
        await self.reserve(request)
        for changes, user in (({"spec_sha256": "b" * 64}, 1), ({"customer_id": 2}, 1), ({}, 2)):
            with self.subTest(changes=changes, user=user), self.assertRaises(ConflictError):
                await self.reserve(request.model_copy(update=changes), user)

    async def test_missing_deleted_and_supplier_contacts_cannot_reserve(self):
        with self.assertRaises(NotFoundError):
            await self.reserve(self.request(customer_id=999))
        for change, expected in (({"type": "supplier"}, ValidationError),
                                 ({"type": "customer", "deleted_at": datetime(2026, 10, 21)}, NotFoundError)):
            with Session(self.engine) as db:
                customer = db.get(Contact, 1)
                for key, value in change.items():
                    setattr(customer, key, value)
                db.commit()
            with self.subTest(change=change), self.assertRaises(expected):
                await self.reserve()

    async def test_reserved_number_cannot_be_claimed_by_another_bill_or_reused_next_year(self):
        reserved = await self.reserve()
        metadata = PdfInvoiceMetadata(
            invoice_number=reserved.invoice_number, invoice_date=DAY, customer_id=1,
            customer_name="Example Buyer", subtotal=100, igst=18, total_amount=118,
            source="generated", line_items=[dict(name="Goods", quantity=1, unit_price=100, tax_rate=18)],
        )
        with Session(self.engine) as db:
            for changes, user in (({"source": "uploaded"}, 1), ({"customer_id": 2}, 1), ({}, 2)):
                with self.subTest(changes=changes, user=user), self.assertRaises(ConflictError):
                    PdfInvoiceService._reserve(db, metadata.model_copy(update=changes), PDF, "bill.pdf", user)
            row = PdfInvoiceService._reserve(db, metadata, PDF, "bill.pdf", 1)
            db.commit()
            again = PdfInvoiceService._reserve(db, metadata, PDF, "bill.pdf", 1)
            self.assertEqual(again.id, row.id)
            with self.assertRaises(ConflictError):
                PdfInvoiceService._reserve(
                    db, metadata.model_copy(update={"invoice_date": date(2027, 10, 21)}),
                    b"%PDF-1.4\nother\n%%EOF", "other.pdf", 1,
                )

    async def test_historical_plain_number_import_remains_distinct_and_does_not_advance_sale_sequence(self):
        with Session(self.engine) as db:
            metadata = PdfInvoiceMetadata(invoice_number="46", invoice_date=DAY, customer_id=1,
                                          customer_name="Example Buyer", subtotal=100, total_amount=100)
            row = PdfInvoiceService._reserve(db, metadata, PDF, "original.pdf", 1)
            db.commit()
            self.assertEqual((row.invoice_number, row.original_filename), ("46", "original.pdf"))
        self.assertEqual((await self.reserve()).invoice_number, "SALE-0001")

    async def test_transaction_signed_download_uses_customer_and_date_without_replacing_archive(self):
        self.transaction("SALE-0046", invoice_url="https://storage.googleapis.com/unit-tests/original.pdf",
                         invoice_checksum="original-checksum")
        with patch.object(StorageService, "generate_presigned_url", return_value="https://signed.invalid") as sign:
            result = await asyncio.wait_for(InvoiceService.generate_presigned_url(1, 60), 3)
        self.assertEqual(result, "https://signed.invalid")
        sign.assert_called_once_with("original.pdf", 60, download_filename="SALE-0046_EXAMPLE-BUYER_2026-10-21.pdf")
        with Session(self.engine) as db:
            self.assertEqual(db.get(Transaction, 1).invoice_checksum, "original-checksum")


class NumberingApiTests(unittest.TestCase):
    def test_reservation_requires_write_role_and_valid_request(self):
        app = FastAPI()
        app.include_router(router)
        request = ReservePdfInvoiceNumber(request_id=uuid4(), customer_id=1, spec_sha256="a" * 64)
        response = PdfInvoiceNumberResponse(**request.model_dump(), invoice_number="SALE-0064")
        with patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden")), \
                patch.object(PdfInvoiceService, "reserve_number", new_callable=AsyncMock, return_value=response) as reserve, \
                TestClient(app) as client:
            self.assertIn(client.post("/pdf-invoices/reserve-number", json=request.model_dump(mode="json")).status_code,
                          (401, 403))
            reserve.assert_not_awaited()
            for role, status in (("JOBBER", 403), ("MANAGER", 403), ("STAFF", 201), ("ADMIN", 201)):
                with self.subTest(role=role):
                    app.dependency_overrides[get_current_user] = lambda role=role: TokenData(1, "staff", role)
                    result = client.post("/pdf-invoices/reserve-number", json=request.model_dump(mode="json"))
                    self.assertEqual(result.status_code, status)
                    if status == 201:
                        self.assertEqual(result.json(), response.model_dump(mode="json"))
                        reserve.assert_awaited_with(request, 1)
            for invalid in ({"customer_id": 0}, {"spec_sha256": "bad"}, {"request_id": "bad"}):
                with self.subTest(invalid=invalid):
                    self.assertEqual(client.post("/pdf-invoices/reserve-number",
                                                 json={**request.model_dump(mode="json"), **invalid}).status_code, 422)


class NumberingCliTests(unittest.TestCase):
    def setUp(self):
        self.spec = GeneratePdfInvoice(
            invoice_date=DAY, customer_id=1, customer_name="Example Buyer", tax_type="igst",
            line_items=[dict(name="Goods", quantity=1, unit_price=100, tax_rate=18)],
        )

    def reservation_response(self, **kwargs):
        response = Mock(status_code=201)
        response.json.return_value = {**kwargs["json"], "invoice_number": "SALE-0064"}
        return response

    def test_timeout_keeps_request_key_and_retry_recovers_same_number(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli, "api_config", return_value=("https://unit-test.invalid/api", "not-a-real-token")), \
                patch.object(cli.requests, "post", side_effect=requests.Timeout("lost response")) as post:
            path = Path(directory)
            with self.assertRaises(requests.Timeout):
                cli.reserve_number(self.spec, path)
            first_request = json.loads((path / "generation-request.json").read_text())
            post.side_effect = lambda *args, **kwargs: self.reservation_response(**kwargs)
            self.assertEqual(cli.reserve_number(self.spec, path), "SALE-0064")
            self.assertEqual(post.call_args.kwargs["json"]["request_id"], first_request["request_id"])
            self.assertNotIn("not-a-real-token", (path / "generation-request.json").read_text())
            self.assertEqual(json.loads((path / "number-reservation.json").read_text())["invoice_number"], "SALE-0064")
            with self.assertRaises(ValueError):
                cli.reserve_number(self.spec.model_copy(update={"customer_name": "Different Buyer"}), path)
            self.assertEqual(post.call_count, 2)

    def test_api_failure_or_mismatched_reservation_never_renders_a_pdf(self):
        for response in (
            Mock(status_code=404, text="Not Found"),
            Mock(status_code=201, json=lambda: dict(
                request_id=str(uuid4()), customer_id=1, spec_sha256="f" * 64, invoice_number="SALE-0064",
            )),
        ):
            with self.subTest(status=response.status_code), tempfile.TemporaryDirectory() as directory, \
                    patch.object(cli, "api_config", return_value=("https://unit-test.invalid/api", "test-token")), \
                    patch.object(cli.requests, "post", return_value=response), \
                    patch.object(cli, "render_invoice") as render:
                with self.assertRaises(RuntimeError):
                    cli.generate(self.spec, Path(directory))
                render.assert_not_called()
                self.assertEqual(list(Path(directory).glob("*.pdf")), [])

    def test_new_generation_rejects_manual_numbers_and_missing_customer_before_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, "reserve_number") as reserve:
            for changes in ({"invoice_number": "46"}, {"invoice_number": "SALE-0064"}, {"customer_id": None}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    cli.generate(self.spec.model_copy(update=changes), Path(directory))
            reserve.assert_not_called()

    def test_preview_neither_reserves_nor_registers_a_number(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, "reserve_number") as reserve, \
                patch.object(cli, "register_pdf") as register, patch.object(cli, "load_seller"), \
                patch("app.modules.pdf_invoices.render.InvoiceGenerator.generate_invoice_pdf", return_value=PDF):
            output = cli.generate(self.spec, Path(directory), preview=True)
            self.assertEqual(output.name, "DRAFT_EXAMPLE-BUYER_2026-10-21.pdf")
            self.assertEqual(output.read_bytes(), PDF)
            reserve.assert_not_called()
            register.assert_not_called()

    def test_generate_reserves_renders_archives_and_retains_descriptive_output(self):
        def post(url, **kwargs):
            if url.endswith("/reserve-number"):
                return self.reservation_response(**kwargs)
            metadata = PdfInvoiceMetadata.model_validate_json(kwargs["data"]["metadata"])
            self.assertEqual(metadata.invoice_number, "SALE-0064")
            self.assertEqual(metadata.customer_id, 1)
            self.assertEqual(kwargs["files"]["file"][0], "SALE-0064_EXAMPLE-BUYER_2026-10-21.pdf")
            self.assertEqual(kwargs["files"]["file"][1], PDF)
            record = PdfInvoiceResponse(
                **metadata.model_dump(), id=1, financial_year="2026-2027",
                original_filename=kwargs["files"]["file"][0], pdf_sha256=hashlib.sha256(PDF).hexdigest(),
                upload_status="ready", created_at=datetime(2026, 10, 21), created_by_id=1,
            )
            return Mock(status_code=201, json=lambda: record.model_dump(mode="json"))

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(cli, "api_config", return_value=("https://unit-test.invalid/api", "test-token")), \
                patch.object(cli.requests, "post", side_effect=post) as upload, \
                patch.object(cli.requests, "get", return_value=Mock(status_code=200, content=PDF)) as download, \
                patch.object(cli, "load_seller"), \
                patch("app.modules.pdf_invoices.render.InvoiceGenerator.generate_invoice_pdf", return_value=PDF):
            output = cli.generate(self.spec, Path(directory))
            self.assertEqual(output.name, "SALE-0064_EXAMPLE-BUYER_2026-10-21.pdf")
            self.assertEqual(output.read_bytes(), PDF)
            self.assertEqual(upload.call_count, 2)
            self.assertEqual(download.call_args.args[0], "https://unit-test.invalid/api/pdf-invoices/1/file")
            receipt = json.loads(output.with_suffix(".registered.json").read_text())
            self.assertEqual(receipt["download_filename"], output.name)
            self.assertEqual(receipt["total_amount"], "118.00")


class SignedFilenameTests(unittest.TestCase):
    def test_signed_url_content_disposition_matches_download_filename(self):
        blob = Mock()
        blob.generate_signed_url.return_value = "https://signed.invalid"
        bucket = Mock()
        bucket.blob.return_value = blob
        with patch.object(StorageService, "_get_bucket", return_value=bucket), \
                patch("google.auth.default", return_value=(SimpleNamespace(), "unit-test")):
            result = StorageService.generate_presigned_url(
                "original.pdf", 60, download_filename="46_AZAD-IMITATION_2026-10-21.pdf",
            )
        self.assertEqual(result, "https://signed.invalid")
        self.assertEqual(blob.generate_signed_url.call_args.kwargs["response_disposition"],
                         'attachment; filename="46_AZAD-IMITATION_2026-10-21.pdf"')


if __name__ == "__main__":
    unittest.main()
