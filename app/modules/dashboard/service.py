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
        """

        def _get_dashboard(db: Session) -> DashboardResponse:
            # 1. Get basic counts
            total_products = db.scalar(
                select(func.count(Product.id)).where(Product.deleted_at.is_(None))
            ) or 0
            
            total_containers = db.scalar(
                select(func.count(Container.id)).where(Container.deleted_at.is_(None))
            ) or 0
            
            total_contacts = db.scalar(
                select(func.count(Contact.id)).where(Contact.deleted_at.is_(None))
            ) or 0
            
            # 2. Get total inventory quantity
            total_inventory = db.scalar(
                select(func.sum(ContainerProduct.quantity)).where(
                    ContainerProduct.deleted_at.is_(None)
                )
            ) or 0
            
            stats = DashboardStatsResponse(
                total_products=total_products,
                total_containers=total_containers,
                total_contacts=total_contacts,
                total_inventory=int(total_inventory),
            )
            
            # 3. Get financial overview from payments
            from app.modules.payments.models import Payment
            
            # Total income (transaction payments for sales + manual income payments)
            total_earnings_query = select(func.sum(Payment.amount)).where(
                Payment.deleted_at.is_(None),
                Payment.type == 'income'
            )
            total_earnings = db.scalar(total_earnings_query) or Decimal('0')
            
            # Total expenses (transaction payments for purchases + manual expense payments)
            total_spends_query = select(func.sum(Payment.amount)).where(
                Payment.deleted_at.is_(None),
                Payment.type == 'expense'
            )
            total_spends = db.scalar(total_spends_query) or Decimal('0')
            
            financial_overview = DashboardFinancialOverviewResponse(
                total_income=total_earnings,
                total_expenses=total_spends,
                net_balance=total_earnings - total_spends,
            )
            
            # 4. Get recent transactions (last 5)
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
