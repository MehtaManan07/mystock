"""
DashboardService - Business logic for aggregating dashboard data.
Efficiently fetches all dashboard data in optimized queries.
"""

from typing import List
from decimal import Decimal
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from .schemas import (
    DashboardResponse,
    DashboardStatsResponse,
    DashboardFinancialOverviewResponse,
    DashboardTransactionResponse,
    DashboardContactResponse,
)
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.contacts.models import Contact
from app.modules.transactions.models import Transaction
from app.modules.container_products.models import ContainerProduct
from app.modules.payments.models import Payment


class DashboardService:
    """
    Dashboard service for aggregating all dashboard data efficiently.
    All methods use run_db() for thread-safe Turso operations.
    """

    @staticmethod
    async def get_dashboard_data() -> DashboardResponse:
        """
        Get all dashboard data in optimized queries.
        Returns aggregated stats, financial overview, recent transactions, and outstanding balances.

        Optimized: 6 scalar subqueries combined into 1 DB roundtrip,
        plus 2 list queries = 3 total queries instead of 8.
        """

        def _get_dashboard(db: Session) -> DashboardResponse:
            # 1. Combine all scalar stats + financial into a single DB roundtrip
            #    using scalar subqueries (6 stats in 1 query instead of 6 separate queries)
            combined_query = select(
                select(func.count(Product.id)).where(Product.deleted_at.is_(None)).correlate(None).scalar_subquery().label('total_products'),
                select(func.count(Container.id)).where(Container.deleted_at.is_(None)).correlate(None).scalar_subquery().label('total_containers'),
                select(func.count(Contact.id)).where(Contact.deleted_at.is_(None)).correlate(None).scalar_subquery().label('total_contacts'),
                select(func.coalesce(func.sum(ContainerProduct.quantity), 0)).where(ContainerProduct.deleted_at.is_(None)).correlate(None).scalar_subquery().label('total_inventory'),
                select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.deleted_at.is_(None), Payment.type == 'income').correlate(None).scalar_subquery().label('total_income'),
                select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.deleted_at.is_(None), Payment.type == 'expense').correlate(None).scalar_subquery().label('total_expenses'),
            )
            row = db.execute(combined_query).one()

            stats = DashboardStatsResponse(
                total_products=row.total_products or 0,
                total_containers=row.total_containers or 0,
                total_contacts=row.total_contacts or 0,
                total_inventory=int(row.total_inventory),
            )

            total_earnings = Decimal(str(row.total_income))
            total_spends = Decimal(str(row.total_expenses))
            financial_overview = DashboardFinancialOverviewResponse(
                total_income=total_earnings,
                total_expenses=total_spends,
                net_balance=total_earnings - total_spends,
            )

            # 2. Get recent transactions (last 5)
            recent_txns_query = (
                select(Transaction)
                .where(Transaction.deleted_at.is_(None))
                .options(selectinload(Transaction.contact))
                .order_by(desc(Transaction.transaction_date), desc(Transaction.id))
                .limit(5)
            )
            recent_txns = db.execute(recent_txns_query).unique().scalars().all()
            
            recent_transactions = [
                DashboardTransactionResponse(
                    id=txn.id,
                    transaction_number=txn.transaction_number,
                    type=txn.type.value,
                    payment_status=txn.payment_status.value,
                    total_amount=txn.total_amount,
                    transaction_date=txn.transaction_date,
                    contact={
                        "id": txn.contact.id,
                        "name": txn.contact.name,
                    } if txn.contact else None,
                )
                for txn in recent_txns
            ]
            
            # 5. Get outstanding contacts (top 5 by absolute balance)
            outstanding_contacts_query = (
                select(Contact)
                .where(
                    Contact.deleted_at.is_(None),
                    Contact.balance != 0
                )
                .order_by(desc(func.abs(Contact.balance)))
                .limit(5)
            )
            outstanding_contacts_list = db.execute(outstanding_contacts_query).scalars().all()
            
            outstanding_contacts = [
                DashboardContactResponse(
                    id=contact.id,
                    name=contact.name,
                    type=contact.type.value,
                    balance=contact.balance,
                )
                for contact in outstanding_contacts_list
            ]
            
            return DashboardResponse(
                stats=stats,
                financial_overview=financial_overview,
                recent_transactions=recent_transactions,
                outstanding_contacts=outstanding_contacts,
            )

        return await run_db(_get_dashboard)
