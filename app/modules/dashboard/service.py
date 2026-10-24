"""Read-only, period-aware dashboard aggregation."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.modules.contacts.models import Contact
from app.modules.container_products.models import ContainerProduct
from app.modules.containers.models import Container
from app.modules.payments.models import Payment
from app.modules.products.models import Product
from app.modules.transactions.models import Transaction, TransactionItem
from .schemas import (
    DashboardBalances,
    DashboardBestSeller,
    DashboardBill,
    DashboardBillContact,
    DashboardCashDay,
    DashboardResponse,
    DashboardPerformance,
    DashboardPeriod,
    DashboardStatsResponse,
    DashboardWindow,
)


def period_window(period: DashboardPeriod, today: date) -> DashboardWindow:
    end = today
    if period == DashboardPeriod.month:
        start = today.replace(day=1)
    elif period == DashboardPeriod.last_month:
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif period == DashboardPeriod.last_90_days:
        start = today - timedelta(days=89)
    else:
        raise ValueError(f"Unsupported dashboard period: {period}")

    # Adjacent, equally long windows never overlap, even in short/leap months.
    days = (end - start).days + 1
    return DashboardWindow(
        start=start,
        end=end,
        comparison_start=start - timedelta(days=days),
        comparison_end=start - timedelta(days=1),
    )


class DashboardService:
    @staticmethod
    async def get_dashboard_data(
        period: DashboardPeriod = DashboardPeriod.month, *, as_of: date | None = None
    ) -> DashboardResponse:
        today = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
        window = period_window(period, today)

        def _read(db: Session) -> DashboardResponse:
            # Aggregate dates in SQL; never download payment/line-item collections.
            payment_days = db.execute(
                select(
                    Payment.payment_date.label("day"),
                    func.sum(case((Payment.type == "income", Payment.amount), else_=0)).label("income"),
                    func.sum(case((Payment.type == "expense", Payment.amount), else_=0)).label("expenses"),
                )
                .where(
                    Payment.deleted_at.is_(None),
                    Payment.payment_date.between(window.comparison_start, window.end),
                )
                .group_by(Payment.payment_date)
            ).all()
            current_income = current_expenses = Decimal(0)
            previous_income = previous_expenses = Decimal(0)
            days_by_date = {}
            for row in payment_days:
                if row.day >= window.start:
                    current_income += row.income
                    current_expenses += row.expenses
                    days_by_date[row.day] = row
                else:
                    previous_income += row.income
                    previous_expenses += row.expenses

            cash_flow = []
            for offset in range((window.end - window.start).days + 1):
                day = window.start + timedelta(days=offset)
                row = days_by_date.get(day)
                cash_flow.append(DashboardCashDay(
                    date=day,
                    income=row.income if row is not None else Decimal(0),
                    expenses=row.expenses if row is not None else Decimal(0),
                ))

            sales = db.execute(
                select(
                    func.coalesce(func.sum(case(
                        (Transaction.transaction_date >= window.start, Transaction.total_amount), else_=0
                    )), 0).label("current_sales"),
                    func.coalesce(func.sum(case(
                        (Transaction.transaction_date < window.start, Transaction.total_amount), else_=0
                    )), 0).label("previous_sales"),
                    func.count(case((Transaction.transaction_date >= window.start, 1))).label("current_count"),
                    func.count(case((Transaction.transaction_date < window.start, 1))).label("previous_count"),
                ).where(
                    Transaction.deleted_at.is_(None),
                    Transaction.type == "sale",
                    Transaction.transaction_date.between(window.comparison_start, window.end),
                )
            ).one()

            # Stock is aggregated before joining sales, so multiple containers or
            # invoice lines cannot multiply either units sold or units on hand.
            stock = (
                select(
                    ContainerProduct.product_id,
                    func.sum(ContainerProduct.quantity).label("quantity"),
                )
                .join(Container, Container.id == ContainerProduct.container_id)
                .join(Product, Product.id == ContainerProduct.product_id)
                .where(
                    ContainerProduct.deleted_at.is_(None),
                    Container.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                )
                .group_by(ContainerProduct.product_id)
                .subquery()
            )
            open_bill = and_(
                Transaction.deleted_at.is_(None),
                Transaction.transaction_date <= today,
                Transaction.total_amount > Transaction.paid_amount,
            )
            snapshot = db.execute(select(
                select(func.count(Product.id)).where(Product.deleted_at.is_(None)).scalar_subquery().label("products"),
                select(func.count(Container.id)).where(Container.deleted_at.is_(None)).scalar_subquery().label("containers"),
                select(func.count(Contact.id)).where(Contact.deleted_at.is_(None)).scalar_subquery().label("contacts"),
                select(func.coalesce(func.sum(stock.c.quantity), 0)).scalar_subquery().label("inventory"),
                select(func.coalesce(func.sum(Contact.balance), 0)).where(
                    Contact.deleted_at.is_(None), Contact.balance > 0
                ).scalar_subquery().label("receivables"),
                select(func.coalesce(func.sum(-Contact.balance), 0)).where(
                    Contact.deleted_at.is_(None), Contact.balance < 0
                ).scalar_subquery().label("payables"),
                select(func.count(Contact.id)).where(
                    Contact.deleted_at.is_(None), Contact.balance > 0
                ).scalar_subquery().label("receivable_accounts"),
                select(func.count(Contact.id)).where(
                    Contact.deleted_at.is_(None), Contact.balance < 0
                ).scalar_subquery().label("payable_accounts"),
                select(func.count(Transaction.id)).where(
                    open_bill, Transaction.type == "sale"
                ).scalar_subquery().label("open_sales"),
                select(func.count(Transaction.id)).where(
                    open_bill, Transaction.type == "purchase"
                ).scalar_subquery().label("open_purchases"),
            )).one()

            # Project columns, rather than hydrating Transaction's eager items and
            # payments. Each list is bounded independently from the full totals.
            bill_query = select(
                Transaction.id,
                Transaction.transaction_number,
                Transaction.type,
                Transaction.payment_status,
                Transaction.transaction_date,
                Transaction.total_amount,
                (Transaction.total_amount - Transaction.paid_amount).label("balance_due"),
                Contact.id.label("contact_id"),
                Contact.name.label("contact_name"),
            ).outerjoin(Contact, and_(
                Contact.id == Transaction.contact_id, Contact.deleted_at.is_(None)
            ))

            def bills(query) -> list[DashboardBill]:
                return [
                    DashboardBill(
                        id=row.id,
                        transaction_number=row.transaction_number,
                        type=row.type.value,
                        payment_status=row.payment_status.value,
                        transaction_date=row.transaction_date,
                        total_amount=row.total_amount,
                        balance_due=row.balance_due,
                        age_days=(today - row.transaction_date).days,
                        contact=DashboardBillContact(id=row.contact_id, name=row.contact_name)
                        if row.contact_id is not None else None,
                    )
                    for row in db.execute(query).all()
                ]

            oldest = bill_query.where(open_bill).order_by(
                Transaction.transaction_date, Transaction.id
            ).limit(5)
            oldest_sales = bills(oldest.where(Transaction.type == "sale"))
            oldest_purchases = bills(oldest.where(Transaction.type == "purchase"))
            recent = bills(
                bill_query.where(
                    Transaction.deleted_at.is_(None), Transaction.transaction_date <= today
                ).order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(5)
            )

            sold = (
                select(
                    TransactionItem.product_id,
                    func.sum(case(
                        (Transaction.transaction_date >= window.start, TransactionItem.quantity), else_=0
                    )).label("units_sold"),
                    func.sum(case(
                        (Transaction.transaction_date < window.start, TransactionItem.quantity), else_=0
                    )).label("previous_units"),
                )
                .join(Transaction, Transaction.id == TransactionItem.transaction_id)
                .where(
                    TransactionItem.deleted_at.is_(None),
                    Transaction.deleted_at.is_(None),
                    Transaction.type == "sale",
                    Transaction.transaction_date.between(window.comparison_start, window.end),
                )
                .group_by(TransactionItem.product_id)
                .subquery()
            )
            # Use the entire sales cohort, not the five ranked products. Historical
            # units include archived products; stock warnings only concern active ones.
            movement = db.execute(
                select(
                    func.coalesce(func.sum(sold.c.units_sold), 0).label("current_units"),
                    func.coalesce(func.sum(sold.c.previous_units), 0).label("previous_units"),
                    func.count(case((and_(
                        sold.c.units_sold > 0,
                        Product.deleted_at.is_(None),
                        func.coalesce(stock.c.quantity, 0) <= 0,
                    ), 1))).label("out_of_stock"),
                )
                .select_from(sold)
                .join(Product, Product.id == sold.c.product_id)
                .outerjoin(stock, stock.c.product_id == sold.c.product_id)
            ).one()
            best_sellers = db.execute(
                select(
                    Product.id, Product.display_name, Product.size, Product.packing,
                    Product.company_sku, sold.c.units_sold,
                    func.coalesce(stock.c.quantity, 0).label("stock_on_hand"),
                )
                .join(sold, sold.c.product_id == Product.id)
                .outerjoin(stock, stock.c.product_id == Product.id)
                .where(Product.deleted_at.is_(None), sold.c.units_sold > 0)
                .order_by(sold.c.units_sold.desc(), Product.id)
                .limit(5)
            ).all()

            return DashboardResponse(
                as_of=today,
                period=period,
                window=window,
                current=DashboardPerformance(
                    sales=sales.current_sales, sale_count=sales.current_count,
                    units_sold=movement.current_units,
                    income=current_income, expenses=current_expenses,
                    net_cash=current_income - current_expenses,
                ),
                previous=DashboardPerformance(
                    sales=sales.previous_sales, sale_count=sales.previous_count,
                    units_sold=movement.previous_units,
                    income=previous_income, expenses=previous_expenses,
                    net_cash=previous_income - previous_expenses,
                ),
                cash_flow=cash_flow,
                balances=DashboardBalances(
                    receivables=snapshot.receivables, payables=snapshot.payables,
                    receivable_accounts=snapshot.receivable_accounts,
                    payable_accounts=snapshot.payable_accounts,
                    open_sales_count=snapshot.open_sales,
                    open_purchases_count=snapshot.open_purchases,
                    oldest_sales=oldest_sales, oldest_purchases=oldest_purchases,
                ),
                best_sellers=[
                    DashboardBestSeller(
                        id=row.id, name=row.display_name, size=row.size, packing=row.packing,
                        company_sku=row.company_sku, units_sold=row.units_sold,
                        stock_on_hand=row.stock_on_hand,
                    ) for row in best_sellers
                ],
                sold_products_out_of_stock=movement.out_of_stock,
                recent_transactions=recent,
                stats=DashboardStatsResponse(
                    total_products=snapshot.products, total_containers=snapshot.containers,
                    total_contacts=snapshot.contacts, total_inventory=snapshot.inventory,
                ),
            )

        return await run_db(_read)
