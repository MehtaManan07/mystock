"""
PaymentsService - Business logic for manual payments management.
Uses the unified Payment model from payments module.
Optimized queries with no extra SQL calls.
"""

from datetime import date
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from .models import Payment, SUGGESTED_PAYMENT_CATEGORIES
from .schemas import CreateManualPaymentDto, UpdateManualPaymentDto, FilterManualPaymentsDto, PaymentSummaryResponse


class PaymentsService:
    """
    Payments service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    Handles manual payments (not linked to transactions).
    """

    @staticmethod
    async def create(db: AsyncSession, create_dto: CreateManualPaymentDto) -> Payment:
        """
        Create a new payment entry.
        Can create either:
        1. Manual payment (transaction_id is None) - requires description and category
        2. Transaction-linked payment (transaction_id is set) - updates transaction paid_amount
        
        Optimized: Single INSERT query.

        Args:
            db: Database session
            create_dto: DTO containing payment information

        Returns:
            Created payment entity

        Raises:
            ValidationError: If validation fails
            NotFoundError: If referenced entities don't exist
        """
        # Validate transaction if provided
        if create_dto.transaction_id:
            from app.modules.transactions.models import Transaction
            transaction_query = select(Transaction).where(
                Transaction.id == create_dto.transaction_id,
                Transaction.deleted_at.is_(None)
            )
            result = await db.execute(transaction_query)
            transaction = result.unique().scalar_one_or_none()
            if not transaction:
                raise NotFoundError("Transaction", create_dto.transaction_id)
            
            # If linking to transaction, set category to transaction_payment if not provided
            if not create_dto.category:
                create_dto.category = "transaction_payment"

            # Derive payment type from transaction type
            if transaction.type.value == "sale":
                create_dto.type = 'income'
            else:
                create_dto.type = 'expense'
        else:
            # For manual payments, require description and category
            if not create_dto.description:
                raise ValidationError("Description is required for manual payments (payments not linked to transactions)")
            if not create_dto.category:
                raise ValidationError("Category is required for manual payments (payments not linked to transactions)")
            if not create_dto.type:
                raise ValidationError("Type is required for manual payments (income or expense)")
        
        # Validate contact if provided
        if create_dto.contact_id:
            from app.modules.contacts.models import Contact
            contact_query = select(Contact).where(
                Contact.id == create_dto.contact_id,
                Contact.deleted_at.is_(None)
            )
            result = await db.execute(contact_query)
            contact = result.scalar_one_or_none()
            if not contact:
                raise NotFoundError("Contact", create_dto.contact_id)

        # Create payment
        payment = Payment(**create_dto.model_dump())
        db.add(payment)
        await db.flush()
        await db.refresh(payment)
        
        # If transaction-linked, update transaction's paid_amount
        if create_dto.transaction_id:
            from app.modules.transactions.models import Transaction, PaymentStatus
            transaction_query = select(Transaction).where(
                Transaction.id == create_dto.transaction_id
            )
            result = await db.execute(transaction_query)
            transaction = result.unique().scalar_one()
            
            # Update paid amount
            transaction.paid_amount += payment.amount
            
            # Update payment status
            if transaction.paid_amount >= transaction.total_amount:
                transaction.payment_status = PaymentStatus.paid
            elif transaction.paid_amount > 0:
                transaction.payment_status = PaymentStatus.partial
            else:
                transaction.payment_status = PaymentStatus.unpaid
            
            await db.flush()
        
        return payment

    @staticmethod
    async def find_all(
        db: AsyncSession,
        filters: Optional[FilterManualPaymentsDto] = None,
    ) -> List[Payment]:
        """
        Find all payments with optional filters.
        By default returns all payments (both manual and transaction-linked).
        Use manual_only=true filter to get only manual payments.
        
        Optimized: Single SELECT query with dynamic filters.

        Args:
            db: Database session
            filters: Optional DTO containing filter criteria

        Returns:
            List of payment entities
        """
        # Base query
        query = select(Payment).where(Payment.deleted_at.is_(None))

        if filters:
            # Apply manual_only filter
            if filters.manual_only:
                query = query.where(Payment.transaction_id.is_(None))
            
            # Apply transaction filter
            if filters.transaction_id:
                query = query.where(Payment.transaction_id == filters.transaction_id)
            
            # Apply type filter
            if getattr(filters, "type", None):
                query = query.where(Payment.type == filters.type)

            # Apply category filter
            if filters.category:
                query = query.where(Payment.category == filters.category)

            # Apply payment method filter
            if filters.payment_method:
                query = query.where(Payment.payment_method == filters.payment_method)

            # Apply contact filter
            if filters.contact_id:
                query = query.where(Payment.contact_id == filters.contact_id)

            # Apply date range filters
            if filters.from_date:
                query = query.where(Payment.payment_date >= filters.from_date)
            if filters.to_date:
                query = query.where(Payment.payment_date <= filters.to_date)

            # Apply amount range filters
            if filters.min_amount is not None:
                query = query.where(Payment.amount >= filters.min_amount)
            if filters.max_amount is not None:
                query = query.where(Payment.amount <= filters.max_amount)

            # Apply search filter
            if filters.search:
                query = query.where(
                    Payment.description.ilike(f"%{filters.search}%")
                    | Payment.notes.ilike(f"%{filters.search}%")
                )

        # Order by payment date descending (most recent first)
        query = query.order_by(Payment.payment_date.desc(), Payment.id.desc())

        result = await db.execute(query)
        payments = result.scalars().all()
        return list(payments)

    @staticmethod
    async def find_one(db: AsyncSession, payment_id: int) -> Payment:
        """
        Find a single payment by id where deleted_at is null.
        Optimized: Single SELECT with composite WHERE clause.

        Args:
            db: Database session
            payment_id: Payment ID to find

        Returns:
            Payment entity

        Raises:
            NotFoundError: If payment not found or is soft-deleted
        """
        result = await db.execute(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.deleted_at.is_(None)
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise NotFoundError("Payment", payment_id)

        return payment

    @staticmethod
    async def update(
        db: AsyncSession, payment_id: int, update_dto: UpdateManualPaymentDto
    ) -> Payment:
        """
        Update payment information.
        Supports updating both manual and transaction-linked payments.
        If updating a transaction-linked payment's amount, updates the transaction's paid_amount.
        
        Optimized: Single UPDATE query, only updates non-None fields.

        Args:
            db: Database session
            payment_id: ID of payment to update
            update_dto: DTO containing fields to update

        Returns:
            Updated payment entity

        Raises:
            NotFoundError: If payment not found or is soft-deleted
            ValidationError: If validation fails
        """
        # Build update dict with only provided values
        update_data = update_dto.model_dump(exclude_unset=True)

        if not update_data:
            # If no fields to update, just return the existing payment
            return await PaymentsService.find_one(db, payment_id)

        # Validate contact if being updated
        if "contact_id" in update_data and update_data["contact_id"] is not None:
            from app.modules.contacts.models import Contact
            contact_query = select(Contact).where(
                Contact.id == update_data["contact_id"],
                Contact.deleted_at.is_(None)
            )
            result = await db.execute(contact_query)
            contact = result.scalar_one_or_none()
            if not contact:
                raise NotFoundError("Contact", update_data["contact_id"])

        # Validate transaction if being updated
        if "transaction_id" in update_data and update_data["transaction_id"] is not None:
            from app.modules.transactions.models import Transaction
            transaction_query = select(Transaction).where(
                Transaction.id == update_data["transaction_id"],
                Transaction.deleted_at.is_(None)
            )
            result = await db.execute(transaction_query)
            transaction = result.unique().scalar_one_or_none()
            if not transaction:
                raise NotFoundError("Transaction", update_data["transaction_id"])
            # Always derive type from transaction if linked
            update_data["type"] = (
                'income' if transaction.type.value == "sale" else 'expense'
            )

        # Get existing payment
        result = await db.execute(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.deleted_at.is_(None)
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise NotFoundError("Payment", payment_id)

        # Track old values for transaction update
        old_transaction_id = payment.transaction_id
        old_amount = payment.amount
        
        # Update payment fields
        for key, value in update_data.items():
            setattr(payment, key, value)

        await db.flush()
        
        # Handle transaction paid_amount updates
        if old_transaction_id or payment.transaction_id:
            from app.modules.transactions.models import Transaction, PaymentStatus
            
            # If moving from one transaction to another
            if old_transaction_id and old_transaction_id != payment.transaction_id:
                # Remove from old transaction
                old_trans_query = select(Transaction).where(Transaction.id == old_transaction_id)
                result = await db.execute(old_trans_query)
                old_trans = result.unique().scalar_one_or_none()
                if old_trans:
                    old_trans.paid_amount -= old_amount
                    # Update payment status
                    if old_trans.paid_amount >= old_trans.total_amount:
                        old_trans.payment_status = PaymentStatus.paid
                    elif old_trans.paid_amount > 0:
                        old_trans.payment_status = PaymentStatus.partial
                    else:
                        old_trans.payment_status = PaymentStatus.unpaid
            
            # Update new/current transaction
            if payment.transaction_id:
                trans_query = select(Transaction).where(Transaction.id == payment.transaction_id)
                result = await db.execute(trans_query)
                transaction = result.unique().scalar_one_or_none()
                if transaction:
                    # Recalculate total paid amount for this transaction
                    payments_query = select(func.sum(Payment.amount)).where(
                        Payment.transaction_id == payment.transaction_id,
                        Payment.deleted_at.is_(None)
                    )
                    result = await db.execute(payments_query)
                    total_paid = result.scalar() or Decimal("0.0")
                    
                    transaction.paid_amount = total_paid
                    
                    # Update payment status
                    if transaction.paid_amount >= transaction.total_amount:
                        transaction.payment_status = PaymentStatus.paid
                    elif transaction.paid_amount > 0:
                        transaction.payment_status = PaymentStatus.partial
                    else:
                        transaction.payment_status = PaymentStatus.unpaid
                    
                    await db.flush()

        await db.refresh(payment)
        return payment

    @staticmethod
    async def remove(db: AsyncSession, payment_id: int) -> None:
        """
        Soft delete a payment by setting deleted_at timestamp.
        If the payment is linked to a transaction, updates the transaction's paid_amount.
        
        Optimized: Single UPDATE query.

        Args:
            db: Database session
            payment_id: ID of payment to soft delete

        Raises:
            NotFoundError: If payment not found or already deleted
        """
        from datetime import datetime

        result = await db.execute(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.deleted_at.is_(None)
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise NotFoundError("Payment", payment_id)

        # If linked to transaction, update transaction's paid_amount
        if payment.transaction_id:
            from app.modules.transactions.models import Transaction, PaymentStatus
            trans_query = select(Transaction).where(Transaction.id == payment.transaction_id)
            result = await db.execute(trans_query)
            transaction = result.unique().scalar_one_or_none()
            if transaction:
                transaction.paid_amount -= payment.amount
                
                # Update payment status
                if transaction.paid_amount >= transaction.total_amount:
                    transaction.payment_status = PaymentStatus.paid
                elif transaction.paid_amount > 0:
                    transaction.payment_status = PaymentStatus.partial
                else:
                    transaction.payment_status = PaymentStatus.unpaid

        payment.deleted_at = datetime.utcnow()
        await db.flush()

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> PaymentSummaryResponse:
        """
        Get summary of manual payments with separate spends and earnings.
        Optimized: Aggregation query with GROUP BY.

        Args:
            db: Database session
            from_date: Optional start date for filtering
            to_date: Optional end date for filtering

        Returns:
            Payment summary with totals separated into spends and earnings
        """
        # Base query - only manual payments
        query = select(
            Payment.type,
            Payment.category,
            func.sum(Payment.amount).label("total_amount"),
            func.count(Payment.id).label("count"),
        ).where(
            Payment.deleted_at.is_(None),
            Payment.transaction_id.is_(None)  # Only manual payments
        )

        # Apply date filters
        if from_date:
            query = query.where(Payment.payment_date >= from_date)
        if to_date:
            query = query.where(Payment.payment_date <= to_date)

        query = query.group_by(Payment.type, Payment.category)

        result = await db.execute(query)
        rows = result.all()

        # Calculate totals - separate spends and earnings
        total_amount = Decimal("0.0")
        total_spends = Decimal("0.0")
        total_earnings = Decimal("0.0")
        payment_count = 0
        category_breakdown = {}

        for row in rows:
            payment_type, category, amount, count = row
            amount = amount or Decimal("0.0")

            total_amount += amount
            payment_count += count

            if payment_type == 'income':
                total_earnings += amount
            else:
                total_spends += amount

            # Add to category breakdown
            if category:
                category_breakdown[category] = float(amount)

        return PaymentSummaryResponse(
            total_amount=total_amount,
            total_spends=total_spends,
            total_earnings=total_earnings,
            payment_count=payment_count,
            category_breakdown=category_breakdown,
        )
