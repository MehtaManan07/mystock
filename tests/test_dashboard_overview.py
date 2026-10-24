"""Offline dashboard regressions. Run only with explicit test permission."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

with patch.dict(os.environ, {
    "POSTGRES_URL": "postgresql+psycopg://localhost:5432/unit-test-invalid",
    "GCP_BUCKET_NAME": "unit-tests",
    "SECRET_KEY": "unit-test-only",
}):
    from app.main import app as application
    from app.core.db.base import Base
    from app.core.db.engine import engine as configured_engine
    from app.core.response_interceptor import SuccessResponseInterceptor
    from app.modules.contacts.models import Contact
    from app.modules.container_products.models import ContainerProduct
    from app.modules.containers.models import Container
    from app.modules.assistant.tools.summary import get_business_summary
    from app.modules.dashboard.router import router
    from app.modules.dashboard.schemas import DashboardPeriod
    from app.modules.dashboard.service import DashboardService, period_window
    from app.modules.payments.models import Payment
    from app.modules.products.models import Product
    from app.modules.transactions.models import Transaction, TransactionItem
    from app.modules.users.auth import TokenData, get_current_user


TODAY = date(2026, 10, 25)
DELETED = datetime(2026, 10, 24, 12)


class DashboardOverviewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        guard = patch.object(configured_engine, "connect", side_effect=AssertionError("Network DB forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.insert(Contact, id=1, name="Example Buyer", phone="Not provided", balance=Decimal("100"))

        async def local_db(fn):
            with Session(self.engine, expire_on_commit=False) as db:
                return fn(db)

        db_patch = patch("app.modules.dashboard.service.run_db", side_effect=local_db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def insert(self, model, **values):
        with Session(self.engine) as db:
            db.execute(model.__table__.insert().values(**values))
            db.commit()

    def transaction(self, identifier=1, **overrides):
        values = dict(
            id=identifier, transaction_number=f"TXN-{identifier}",
            transaction_date=TODAY, contact_id=1, type="sale",
            payment_status="unpaid", subtotal=1000, total_amount=1000, paid_amount=0,
        )
        values.update(overrides)
        self.insert(Transaction, **values)

    def payment(self, identifier=1, **overrides):
        values = dict(
            id=identifier, payment_date=TODAY, amount=Decimal("100"),
            payment_method="cash", type="income",
        )
        values.update(overrides)
        self.insert(Payment, **values)

    async def overview(self, period=DashboardPeriod.month):
        return await DashboardService.get_dashboard_data(period, as_of=TODAY)

    def test_period_windows_are_equal_adjacent_and_include_leap_day(self):
        cases = [
            (DashboardPeriod.month, date(2026, 10, 25), date(2026, 10, 1), date(2026, 10, 25)),
            (DashboardPeriod.month, date(2026, 3, 31), date(2026, 3, 1), date(2026, 3, 31)),
            (DashboardPeriod.month, date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 1)),
            (DashboardPeriod.last_month, date(2024, 3, 3), date(2024, 2, 1), date(2024, 2, 29)),
            (DashboardPeriod.last_month, date(2026, 1, 10), date(2025, 12, 1), date(2025, 12, 31)),
            (DashboardPeriod.last_90_days, TODAY, date(2026, 7, 28), TODAY),
        ]
        for period, today, start, end in cases:
            with self.subTest(period=period, today=today):
                window = period_window(period, today)
                self.assertEqual((window.start, window.end), (start, end))
                self.assertEqual(window.comparison_end + timedelta(days=1), start)
                self.assertEqual(end - start, window.comparison_end - window.comparison_start)
        with self.assertRaises(ValueError):
            period_window("unsupported", TODAY)

    async def test_empty_data_is_zero_filled_without_fake_trends(self):
        result = await self.overview()
        self.assertEqual(len(result.cash_flow), 25)
        self.assertEqual(result.cash_flow[0].date, date(2026, 10, 1))
        self.assertEqual(result.cash_flow[-1].date, TODAY)
        self.assertTrue(all(day.income == day.expenses == 0 for day in result.cash_flow))
        self.assertEqual(result.current.sales, 0)
        self.assertEqual((result.current.units_sold, result.previous.units_sold), (0, 0))
        self.assertEqual(result.sold_products_out_of_stock, 0)
        self.assertEqual(result.previous.net_cash, 0)
        self.assertEqual(result.best_sellers, [])
        self.assertEqual(result.recent_transactions, [])

    async def test_default_business_date_uses_india_timezone(self):
        with patch("app.modules.dashboard.service.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 25, 1, 0)
            result = await DashboardService.get_dashboard_data()
            self.assertEqual(clock.now.call_args.args[0].key, "Asia/Kolkata")
            self.assertEqual(result.as_of, TODAY)

    async def test_assistant_uses_the_new_contract_and_explicit_periods(self):
        self.payment(1, amount=5000, payment_date=date(2020, 1, 1))
        self.payment(2, amount=100)
        self.transaction(payment_status="partial", paid_amount=250)
        self.transaction(2, type="purchase", paid_amount=100, payment_status="partial")
        with patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}):
            for period in DashboardPeriod:
                response = await self.overview(period)
                with patch.object(
                    DashboardService, "get_dashboard_data", new=AsyncMock(return_value=response)
                ) as service:
                    args = {} if period == DashboardPeriod.month else {"period": period.value}
                    text = await get_business_summary.ainvoke(args)
                    service.assert_awaited_once_with(period)
                    self.assertIn(f"PERIOD PERFORMANCE ({response.window.start} to {response.window.end})", text)
                    self.assertIn("CURRENT ACCOUNT BALANCES (all dates;", text)
                    self.assertIn("Rs 750 still due", text)
                    self.assertIn("Rs 900 still due", text)
                    self.assertIn("TXN-1 | sale | Example Buyer", text)
                    self.assertIn("age is not overdue status", text)
                    self.assertNotIn("FINANCIALS (to date)", text)
                    if period == DashboardPeriod.month:
                        self.assertIn("Money received: Rs 100", text)
                        self.assertNotIn("Rs 5,100", text)
            with patch.object(DashboardService, "get_dashboard_data", new=AsyncMock()) as service:
                with self.assertRaises(ValidationError):
                    await get_business_summary.ainvoke({"period": "all_time"})
                service.assert_not_awaited()

    async def test_cash_uses_payment_dates_and_preserves_decimal_amounts(self):
        self.transaction(transaction_date=date(2026, 8, 1))
        self.payment(1, amount=Decimal("0.10"), payment_date=date(2026, 10, 1))
        self.payment(2, amount=Decimal("0.20"), payment_date=date(2026, 10, 1))
        self.payment(3, amount=200, transaction_id=1, payment_date=date(2026, 10, 2))
        self.payment(4, amount=50, type="expense")
        self.payment(5, amount=75, payment_date=date(2026, 9, 6))
        self.payment(6, amount=25, type="expense", payment_date=date(2026, 9, 30))
        self.payment(7, amount=999, deleted_at=DELETED)
        self.payment(8, amount=999, payment_date=date(2026, 10, 26))
        self.payment(9, amount=999, payment_date=date(2026, 9, 5))
        self.transaction(2, total_amount=5500)
        self.transaction(3, total_amount=100, transaction_date=date(2026, 9, 30))
        self.transaction(4, type="purchase", total_amount=999)
        self.transaction(5, deleted_at=DELETED, total_amount=999)
        result = await self.overview()
        self.assertEqual(result.current.income, Decimal("200.30"))
        self.assertEqual(result.current.expenses, Decimal("50"))
        self.assertEqual(result.current.net_cash, Decimal("150.30"))
        self.assertEqual(result.previous.income, Decimal("75"))
        self.assertEqual(result.previous.expenses, Decimal("25"))
        self.assertEqual(result.current.sales, Decimal("5500"))
        self.assertEqual(result.current.sale_count, 1)
        self.assertEqual(result.previous.sales, Decimal("100"))
        self.assertEqual(result.cash_flow[0].income, Decimal("0.30"))
        self.assertEqual(sum(day.income for day in result.cash_flow), result.current.income)
        self.assertEqual(sum(day.expenses for day in result.cash_flow), result.current.expenses)
        self.assertEqual(result.model_dump(mode="json")["current"]["income"], "200.30")

    async def test_last_month_and_90_day_aggregates_match_their_windows(self):
        self.payment(1, amount=10, payment_date=date(2026, 7, 28))
        self.payment(2, amount=20, payment_date=date(2026, 9, 30))
        self.payment(3, amount=30, payment_date=TODAY)
        self.payment(4, amount=40, payment_date=date(2026, 7, 27))
        month = await self.overview(DashboardPeriod.last_month)
        quarter = await self.overview(DashboardPeriod.last_90_days)
        self.assertEqual((month.current.income, len(month.cash_flow)), (20, 30))
        self.assertEqual((quarter.current.income, len(quarter.cash_flow)), (60, 90))
        self.assertEqual(quarter.previous.income, 40)

    async def test_account_totals_include_every_account_not_just_top_five(self):
        for identifier in range(2, 10):
            self.insert(Contact, id=identifier, name=f"Buyer {identifier}", phone="Not provided", balance=100)
        self.insert(Contact, id=10, name="Supplier", phone="Not provided", balance=-250)
        self.insert(Contact, id=11, name="Other supplier", phone="Not provided", balance=-500)
        self.insert(Contact, id=12, name="Archived", phone="Not provided", balance=999, deleted_at=DELETED)
        result = await self.overview()
        self.assertEqual((result.balances.receivables, result.balances.receivable_accounts), (900, 9))
        self.assertEqual((result.balances.payables, result.balances.payable_accounts), (750, 2))
        self.assertEqual(result.stats.total_contacts, 11)
        other_period = await self.overview(DashboardPeriod.last_month)
        self.assertEqual(other_period.balances, result.balances)

    async def test_oldest_bills_use_remaining_amounts_and_stable_order(self):
        for identifier in range(1, 8):
            self.transaction(identifier, transaction_date=date(2026, 8, identifier))
        self.transaction(8, type="purchase", transaction_date=date(2026, 7, 1),
                         payment_status="partial", paid_amount=275)
        self.transaction(9, transaction_date=date(2026, 1, 1), paid_amount=1000, payment_status="paid")
        self.transaction(10, transaction_date=date(2026, 1, 1), deleted_at=DELETED)
        self.transaction(11, transaction_date=date(2026, 10, 26))
        self.transaction(12, transaction_date=date(2026, 8, 1), payment_status="partial", paid_amount=100)
        result = await self.overview()
        self.assertEqual([bill.id for bill in result.balances.oldest_sales], [1, 12, 2, 3, 4])
        self.assertEqual(result.balances.open_sales_count, 8)
        self.assertEqual(result.balances.oldest_sales[1].balance_due, 900)
        self.assertEqual(result.balances.oldest_purchases[0].balance_due, 725)
        self.assertEqual(result.balances.oldest_purchases[0].age_days, (TODAY - date(2026, 7, 1)).days)
        self.assertEqual(result.balances.open_purchases_count, 1)
        self.assertEqual([bill.id for bill in result.recent_transactions], [7, 6, 5, 4, 3])
        other_period = await self.overview(DashboardPeriod.last_month)
        self.assertEqual(other_period.balances, result.balances)

    async def test_best_sellers_do_not_multiply_stock_or_sales(self):
        for identifier in (1, 2, 3):
            self.insert(Product, id=identifier, name=f"Product {identifier}", display_name=f"Product {identifier}",
                        size="M", packing="Each", deleted_at=DELETED if identifier == 3 else None)
        for identifier in (1, 2, 3):
            self.insert(Container, id=identifier, name=f"Container {identifier}", type="mixed",
                        deleted_at=DELETED if identifier == 3 else None)
        self.insert(ContainerProduct, container_id=1, product_id=1, quantity=10)
        self.insert(ContainerProduct, container_id=2, product_id=1, quantity=20)
        self.insert(ContainerProduct, container_id=3, product_id=1, quantity=999)
        self.insert(ContainerProduct, container_id=1, product_id=2, quantity=999, deleted_at=DELETED)
        self.insert(ContainerProduct, container_id=1, product_id=3, quantity=999)
        self.transaction()
        self.transaction(2, type="purchase")
        self.transaction(3, deleted_at=DELETED)
        self.transaction(4, transaction_date=date(2026, 9, 1))
        for txn_id, product_id, quantity, deleted in [
            (1, 1, 3, None), (1, 1, 4, None), (1, 2, 2, None),
            (1, 3, 999, None), (2, 1, 999, None), (3, 1, 999, None),
            (4, 1, 999, None), (1, 1, 999, DELETED),
        ]:
            self.insert(TransactionItem, transaction_id=txn_id, product_id=product_id,
                        quantity=quantity, unit_price=1, line_total=quantity, deleted_at=deleted)
        result = await self.overview()
        self.assertEqual([(p.id, p.units_sold, p.stock_on_hand) for p in result.best_sellers],
                         [(1, 7, 30), (2, 2, 0)])
        self.assertEqual((result.stats.total_inventory, result.stats.total_products, result.stats.total_containers),
                         (30, 2, 2))
        self.assertEqual(result.current.units_sold, 1008)
        self.assertEqual(result.sold_products_out_of_stock, 1)
        self.assertEqual((result.current.sales, result.current.sale_count), (1000, 1))

    async def test_units_and_stock_gaps_cover_the_full_cohort_and_exact_windows(self):
        for identifier in range(1, 11):
            self.insert(Product, id=identifier, name=f"Product {identifier}", display_name=f"Product {identifier}",
                        size="M", packing="Each", deleted_at=DELETED if identifier == 10 else None)
        self.insert(Container, id=1, name="Active container", type="mixed")
        self.insert(Container, id=2, name="Archived container", type="mixed", deleted_at=DELETED)
        for product_id in range(1, 6):
            self.insert(ContainerProduct, product_id=product_id, container_id=1, quantity=10)
        self.insert(ContainerProduct, product_id=7, container_id=1, quantity=-1)
        self.insert(ContainerProduct, product_id=8, container_id=2, quantity=50)
        self.transaction(1)
        self.transaction(2, transaction_date=date(2026, 9, 6))
        self.transaction(3, transaction_date=date(2026, 9, 30))
        self.transaction(4, transaction_date=date(2026, 10, 26))
        self.transaction(5, transaction_date=date(2026, 9, 5))
        self.transaction(6, deleted_at=DELETED)
        self.transaction(7, type="purchase")
        for product_id in range(1, 9):
            quantity = 100 - product_id * 10
            self.insert(TransactionItem, transaction_id=1, product_id=product_id,
                        quantity=quantity, unit_price=1, line_total=quantity)
        for txn_id, product_id, quantity, deleted in [
            (1, 10, 5, None), (2, 9, 1000, None), (3, 1, 17, None),
            (4, 1, 999, None), (5, 1, 999, None), (6, 1, 999, None),
            (7, 1, 999, None), (1, 1, 999, DELETED),
        ]:
            self.insert(TransactionItem, transaction_id=txn_id, product_id=product_id,
                        quantity=quantity, unit_price=1, line_total=quantity, deleted_at=deleted)
        result = await self.overview()
        self.assertEqual((result.current.units_sold, result.previous.units_sold), (445, 1017))
        self.assertEqual(result.sold_products_out_of_stock, 3)
        self.assertEqual([product.id for product in result.best_sellers], [1, 2, 3, 4, 5])
        self.assertTrue(all(product.stock_on_hand > 0 for product in result.best_sellers))
        self.assertEqual((result.current.sales, result.current.sale_count), (1000, 1))

    async def test_overview_only_executes_selects_and_has_bounded_query_count(self):
        self.transaction()
        queries = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            queries.append(statement)
            self.assertTrue(statement.lstrip().upper().startswith("SELECT"), statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            await self.overview()
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(len(queries), 8)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(Transaction.paid_amount)), 0)

    async def test_route_auth_period_validation_and_serialized_contract(self):
        api = FastAPI()
        api.include_router(router, prefix="/api")
        api.add_middleware(SuccessResponseInterceptor)
        response = await self.overview()
        with TestClient(api) as client, patch.object(
            DashboardService, "get_dashboard_data", new=AsyncMock(return_value=response)
        ) as service:
            self.assertEqual(client.get("/api/dashboard").status_code, 403)
            service.assert_not_awaited()
            api.dependency_overrides[get_current_user] = lambda: TokenData(1, "tester", "ADMIN")
            self.assertEqual(client.get("/api/dashboard?period=invalid").status_code, 422)
            service.assert_not_awaited()
            result = client.get("/api/dashboard?period=month")
            self.assertEqual(result.status_code, 200)
            payload = result.json()["data"]
            self.assertEqual(payload["period"], "month")
            self.assertEqual(payload["window"]["start"], "2026-10-01")
            self.assertEqual(payload["cash_flow"][0]["date"], "2026-10-01")
            self.assertIsInstance(payload["current"]["sales"], str)
            self.assertEqual(payload["current"]["units_sold"], 0)
            self.assertEqual(payload["sold_products_out_of_stock"], 0)
            self.assertNotIn("financial_overview", payload)
            service.assert_awaited_once_with(DashboardPeriod.month)
            service.reset_mock()
            self.assertEqual(client.get("/api/dashboard").status_code, 200)
            service.assert_awaited_once_with(DashboardPeriod.month)
            self.assertEqual(client.get("/api/dashboard/overview").status_code, 404)
            api.dependency_overrides[get_current_user] = lambda: TokenData(1, "tester", "UNAUTHORIZED")
            self.assertEqual(client.get("/api/dashboard").status_code, 403)


if __name__ == "__main__":
    unittest.main()
