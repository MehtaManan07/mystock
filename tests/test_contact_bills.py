"""Offline contact-bill regressions. Run only with explicit test permission."""
from datetime import date, datetime
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

with patch.dict(os.environ, {
    "POSTGRES_URL": "postgresql+psycopg://localhost:5432/unit-test-invalid",
    "GCP_BUCKET_NAME": "unit-tests",
    "SECRET_KEY": "unit-test-only",
}):
    from app.main import app as application
    from app.core.db.base import Base
    from app.core.db.engine import engine as configured_engine
    from app.core.exceptions import NotFoundError
    from app.modules.contacts.bills import ContactBillsService
    from app.modules.contacts.models import Contact
    from app.modules.contacts.router import router
    from app.modules.contacts.schemas import ContactBillPage
    from app.modules.pdf_invoices.models import PdfInvoice
    from app.modules.transactions.models import Transaction
    from app.modules.users.auth import TokenData, get_current_user


GSTIN = "24ABCDE1234F1Z5"
CREATED_AT = datetime(2026, 10, 20, 12)


class ContactBillsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        guard = patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                Contact(id=1, name="Example Buyer", gstin=GSTIN, phone="Not provided", balance=Decimal("17.00")),
                Contact(id=2, name="Other Buyer", gstin="07ABCDE1234F1Z5", phone="Not provided"),
            ])
            db.commit()

        async def local_db(fn):
            with Session(self.engine, expire_on_commit=False) as db:
                result = fn(db)
                db.commit()
                return result

        db_patch = patch("app.modules.contacts.bills.run_db", side_effect=local_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def pdf(self, identifier=1, **overrides):
        values = dict(
            id=identifier, invoice_number=f"PDF-{identifier}", invoice_date=date(2026, 10, 20),
            financial_year="2026-2027", customer_name="Example Buyer", customer_gstin=GSTIN,
            customer_id=1,
            subtotal=Decimal("100"), cgst=0, sgst=0, igst=5, round_off=0, total_amount=105,
            source="uploaded", original_filename="bill.pdf", pdf_sha256=f"{identifier:064x}",
            metadata_sha256="a" * 64, storage_key=f"unit-tests/{identifier}.pdf",
            upload_status="ready", created_by_id=1, created_at=CREATED_AT,
        )
        values.update(overrides)
        with Session(self.engine) as db:
            db.add(PdfInvoice(**values))
            db.commit()

    def transaction(self, identifier=1, **overrides):
        values = dict(
            id=identifier, transaction_number=f"SALE-{identifier}", transaction_date=date(2026, 10, 20),
            contact_id=1, type="sale", payment_status="unpaid", subtotal=100, total_amount=105,
            created_at=CREATED_AT,
        )
        values.update(overrides)
        with Session(self.engine) as db:
            db.execute(Transaction.__table__.insert().values(**values))
            db.commit()

    def contact(self, identifier=1, **values):
        with Session(self.engine) as db:
            row = db.get(Contact, identifier)
            for key, value in values.items():
                setattr(row, key, value)
            db.commit()

    def database_rows(self):
        with Session(self.engine) as db:
            return {
                table.name: [dict(row) for row in db.execute(select(table)).mappings()]
                for table in Base.metadata.sorted_tables
            }

    async def test_combines_sales_purchases_and_pdf_bills_without_writes(self):
        self.transaction(transaction_date=date(2026, 10, 20))
        self.pdf(invoice_date=date(2026, 10, 19), customer_name="Different trade name")
        self.transaction(2, type="purchase", payment_status="paid", transaction_date=date(2026, 10, 18))
        self.transaction(3, contact_id=2)
        before = self.database_rows()

        page = await ContactBillsService.list_bills(1, 1, 2)
        self.assertEqual([(row.source, row.id) for row in page.items], [("transaction", 1), ("pdf_invoice", 1)])
        self.assertEqual((page.total, page.page, page.page_size, page.has_more), (3, 1, 2, True))
        self.assertEqual(page.items[0].payment_status, "unpaid")
        self.assertEqual(page.items[0].transaction_type, "sale")
        self.assertIsNone(page.items[1].payment_status)
        self.assertEqual(page.items[1].upload_status, "ready")
        self.assertEqual(page.items[1].model_dump(mode="json")["total_amount"], "105.00")

        next_page = await ContactBillsService.list_bills(1, 2, 2)
        self.assertEqual([(row.source, row.id) for row in next_page.items], [("transaction", 2)])
        self.assertEqual(next_page.items[0].transaction_type, "purchase")
        self.assertFalse(next_page.has_more)
        self.assertEqual(before, self.database_rows())

    async def test_contact_edits_do_not_change_historical_links(self):
        self.pdf(customer_name="Old legal name")
        self.contact(name="Renamed customer", gstin=None)
        page = await ContactBillsService.list_bills(1, 1, 25)
        self.assertEqual([row.id for row in page.items], [1])

    async def test_same_name_and_gstin_do_not_override_the_stored_customer_id(self):
        self.pdf(customer_id=2)
        self.pdf(2, customer_id=None)
        page = await ContactBillsService.list_bills(1, 1, 25)
        self.assertEqual((page.items, page.total), ([], 0))
        other = await ContactBillsService.list_bills(2, 1, 25)
        self.assertEqual([row.id for row in other.items], [1])

    async def test_duplicate_names_do_not_hide_linked_bills(self):
        self.contact(gstin=None)
        self.contact(2, name=" example buyer ")
        self.pdf(customer_gstin=None)
        self.transaction()
        page = await ContactBillsService.list_bills(1, 1, 25)
        self.assertEqual([(row.source, row.id) for row in page.items], [("pdf_invoice", 1), ("transaction", 1)])

    def test_backfill_links_unique_identities_and_preserves_snapshots(self):
        self.contact(2, name="Unregistered Buyer", gstin=None)
        self.pdf(customer_id=None, customer_gstin=f" {GSTIN.lower()} ", customer_name="Old name")
        self.pdf(2, customer_id=None, customer_gstin=None, customer_name=" unregistered buyer ")
        self.pdf(3, customer_id=None, customer_gstin="07ABCDE1234F1Z5")
        self.pdf(4, customer_id=None, deleted_at=CREATED_AT)
        self.pdf(5, customer_id=2)
        before = self.database_rows()
        self.backfill()
        with Session(self.engine) as db:
            self.assertEqual(db.scalars(select(PdfInvoice.customer_id).order_by(PdfInvoice.id)).all(),
                             [1, 2, None, 1, 2])
        after = self.database_rows()
        for snapshots in (before, after):
            for row in snapshots["pdf_invoices"]:
                row.pop("customer_id")
        self.assertEqual(before, after)

    def test_backfill_does_not_guess_duplicate_or_missing_identities(self):
        self.contact(2, name="Example Buyer", gstin=GSTIN)
        self.pdf(customer_id=None)
        self.pdf(2, customer_id=None, customer_gstin=None)
        self.pdf(3, customer_id=None, customer_gstin=None, customer_name="Unknown")
        self.backfill()
        with Session(self.engine) as db:
            self.assertEqual(db.scalars(select(PdfInvoice.customer_id)).all(), [None, None, None])
        self.contact(2, deleted_at=CREATED_AT)
        self.backfill()
        with Session(self.engine) as db:
            self.assertEqual(db.scalars(select(PdfInvoice.customer_id).order_by(PdfInvoice.id)).all(),
                             [1, None, None])

    def backfill(self):
        path = Path(__file__).resolve().parents[1] / "alembic/versions/0018_pdf_invoice_customer.py"
        spec = importlib.util.spec_from_file_location("pdf_customer_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        # The schema is already created above; exercise the migration's actual data SQL.
        with Session(self.engine) as db, patch.object(migration, "op") as operations:
            operations.execute.side_effect = db.execute
            migration.upgrade()
            db.commit()

    async def test_pending_is_visible_and_retired_records_are_excluded(self):
        self.pdf(upload_status="pending")
        self.pdf(2, deleted_at=CREATED_AT)
        self.transaction(deleted_at=CREATED_AT)
        page = await ContactBillsService.list_bills(1, 1, 25)
        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].upload_status, "pending")
        self.assertIsNone(page.items[0].payment_status)

    async def test_pagination_reaches_all_rows_with_stable_cross_source_ties(self):
        for identifier in range(1, 32):
            self.pdf(identifier)
        for identifier in range(1, 31):
            self.transaction(identifier)
        pages = [await ContactBillsService.list_bills(1, page, 25) for page in (1, 2, 3)]
        actual = [(row.source, row.id) for page in pages for row in page.items]
        expected = ([("pdf_invoice", identifier) for identifier in range(31, 0, -1)]
                    + [("transaction", identifier) for identifier in range(30, 0, -1)])
        self.assertEqual(actual, expected)
        self.assertEqual([page.total for page in pages], [61, 61, 61])
        self.assertEqual([page.has_more for page in pages], [True, True, False])
        repeat = await ContactBillsService.list_bills(1, 2, 25)
        self.assertEqual(repeat, pages[1])
        empty = await ContactBillsService.list_bills(1, 4, 25)
        self.assertEqual((empty.items, empty.total, empty.has_more), ([], 61, False))

    async def test_missing_and_deleted_contacts_are_not_found(self):
        with self.assertRaises(NotFoundError):
            await ContactBillsService.list_bills(999, 1, 25)
        self.contact(deleted_at=CREATED_AT)
        with self.assertRaises(NotFoundError):
            await ContactBillsService.list_bills(1, 1, 25)


class ContactBillsApiTests(unittest.TestCase):
    def test_authentication_and_pagination_contract(self):
        app = FastAPI()
        app.include_router(router)
        result = ContactBillPage(items=[], total=0, page=2, page_size=10, has_more=False)
        with patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden")), \
                patch.object(ContactBillsService, "list_bills", new_callable=AsyncMock, return_value=result) as read, \
                TestClient(app) as client:
            self.assertIn(client.get("/contacts/1/bills").status_code, (401, 403))
            read.assert_not_awaited()
            for role in ("ADMIN", "STAFF", "MANAGER", "JOBBER"):
                with self.subTest(role=role):
                    app.dependency_overrides[get_current_user] = lambda role=role: TokenData(1, "reader", role)
                    response = client.get("/contacts/1/bills?page=2&page_size=10")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), result.model_dump(mode="json"))
                    read.assert_awaited_with(1, 2, 10)
            for query in ("page=0", "page_size=0", "page_size=101"):
                with self.subTest(query=query):
                    self.assertEqual(client.get(f"/contacts/1/bills?{query}").status_code, 422)


if __name__ == "__main__":
    unittest.main()
