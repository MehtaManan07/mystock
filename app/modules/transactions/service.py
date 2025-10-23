"""
TransactionsService - Business logic for sales and purchase transactions.
Handles inventory updates, payment tracking, and contact balance management.
"""

from typing import List, Optional, Dict, Tuple, cast
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, desc, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ValidationError, NotFoundError
from .models import (
    Transaction,
    TransactionItem,
    Payment,
    TransactionType,
    PaymentStatus,
    PaymentMethod,
)
from .schemas import (
    CreateSaleDto,
    CreatePurchaseDto,
    CreatePaymentDto,
    TransactionFilterDto,
)
from app.modules.contacts.models import Contact, ContactType
from app.modules.contacts.service import ContactsService
from app.modules.products.models import Product
from app.modules.products.service import ProductService
from app.modules.containers.models import Container
from app.modules.container_products.models import ContainerProduct
from app.modules.container_products.service import ContainerProductService
from app.modules.inventory_logs.models import InventoryLog


class TransactionsService:
    """
    Transactions service for managing sales and purchases.
    Handles complex business logic with proper locking and audit trails.
    """

    @staticmethod
    async def _generate_transaction_number(
        db: AsyncSession, transaction_type: TransactionType
    ) -> str:
        """
        Generate unique transaction number based on type.
        Format: SALE-0001, SALE-0002 or PUR-0001, PUR-0002

        Args:
            db: Database session
            transaction_type: Type of transaction (sale or purchase)

        Returns:
            Generated transaction number (e.g., "SALE-0001")
        """
        prefix = "SALE" if transaction_type == TransactionType.sale else "PUR"

        # Get the last transaction of this type
        query = (
            select(Transaction)
            .where(Transaction.type == transaction_type)
            .order_by(desc(Transaction.id))
            .limit(1)
        )

        result = await db.execute(query)
        last_transaction = result.scalar_one_or_none()

        if not last_transaction:
            # First transaction of this type
            return f"{prefix}-0001"

        # Extract the number from last transaction and increment
        # Expected format: "SALE-0001" or "PUR-0001"
        try:
            last_number = int(last_transaction.transaction_number.split("-")[1])
            new_number = last_number + 1
            return f"{prefix}-{new_number:04d}"
        except (IndexError, ValueError):
            # Fallback if format is unexpected
            return f"{prefix}-0001"

    @staticmethod
    async def create_sale(db: AsyncSession, sale_data: CreateSaleDto) -> Transaction:
        """
        Create a new sale transaction with inventory deduction.
        Uses delegated service methods for clean architecture.

        Business Logic:
        1. Validate contact is customer or both (delegated)
        2. Validate all products exist (delegated)
        3. Validate all containers have sufficient stock (delegated)
        4. Create transaction with auto-generated number
        5. Create transaction items
        6. Deduct inventory from containers
        7. Create inventory logs
        8. Update contact balance (delegated)
        9. Create payment record if paid_amount > 0

        Args:
            db: Database session
            sale_data: Sale creation data

        Returns:
            Created transaction with all relationships

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contact/product/container not found
        """

        # STEP 1: Validate Contact (Delegated to ContactsService)
        # Single DB query, returns validated contact
        contact = await ContactsService.validate_for_sale(db, sale_data.contact_id)

        # STEP 2: Validate Products (Delegated to ProductsService)
        # Single batched DB query, returns dict of products
        product_ids = [item.product_id for item in sale_data.items]
        products_dict = await ProductService.validate_products_exist(db, product_ids)

        # STEP 3: Validate Container Stock (Delegated to ContainerProductService)
        # Validate container_id provided for all items
        for item in sale_data.items:
            if not item.container_id:
                raise ValidationError(
                    f"Container ID is required for sales of product ID {item.product_id}"
                )

        # Single batched DB query, returns dict of container-products
        # Type assertion: all container_ids are guaranteed non-None from validation above
        pairs: List[Tuple[int, int]] = [
            (item.product_id, cast(int, item.container_id)) for item in sale_data.items
        ]
        container_product_map = await ContainerProductService.validate_and_get_stock(
            db, pairs
        )

        # Validate sufficient stock (using pre-fetched data, no DB calls)
        for item in sale_data.items:
            assert item.container_id is not None
            key = (item.product_id, item.container_id)
            container_product = container_product_map[key]

            if container_product.quantity < item.quantity:
                product_name = products_dict[item.product_id].name
                raise ValidationError(
                    f"Insufficient stock for '{product_name}'. "
                    f"Available: {container_product.quantity}, Required: {item.quantity}"
                )

        # STEP 4: Calculate Totals (Pure logic, no DB calls)
        subtotal = sum(item.quantity * item.unit_price for item in sale_data.items)
        total_amount = subtotal + sale_data.tax_amount - sale_data.discount_amount

        if sale_data.paid_amount > total_amount:
            raise ValidationError(
                f"Paid amount ({sale_data.paid_amount}) cannot exceed total ({total_amount})"
            )

        # Determine payment status
        if sale_data.paid_amount == 0:
            payment_status = PaymentStatus.unpaid
        elif sale_data.paid_amount >= total_amount:
            payment_status = PaymentStatus.paid
        else:
            payment_status = PaymentStatus.partial

        # STEP 5: Generate Transaction Number (Helper method)
        transaction_number = await TransactionsService._generate_transaction_number(
            db, TransactionType.sale
        )

        # STEP 6: Create Transaction Record
        transaction = Transaction(
            transaction_number=transaction_number,
            transaction_date=sale_data.transaction_date,
            type=TransactionType.sale,
            contact_id=sale_data.contact_id,
            subtotal=subtotal,
            tax_amount=sale_data.tax_amount,
            discount_amount=sale_data.discount_amount,
            total_amount=total_amount,
            paid_amount=sale_data.paid_amount,
            payment_status=payment_status,
            notes=sale_data.notes,
        )
        db.add(transaction)
        await db.flush()  # Get transaction.id

        # STEP 7: Create Items & Update Inventory (Bulk operations)
        transaction_items = []
        inventory_logs = []

        for item in sale_data.items:
            # Create transaction item
            line_total = item.quantity * item.unit_price
            transaction_items.append(
                TransactionItem(
                    transaction_id=transaction.id,
                    product_id=item.product_id,
                    container_id=item.container_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=line_total,
                )
            )

            # Update stock (in-memory, using pre-fetched data)
            assert item.container_id is not None
            key = (item.product_id, item.container_id)
            container_product = container_product_map[key]
            old_qty = container_product.quantity
            container_product.quantity -= item.quantity

            # Create inventory log
            inventory_logs.append(
                InventoryLog(
                    product_id=item.product_id,
                    container_id=item.container_id,
                    action="sale",
                    quantity=-item.quantity,  # Negative for sales
                    note=f"Sale {transaction_number} - {old_qty} → {container_product.quantity}",
                )
            )

        # Bulk insert
        db.add_all(transaction_items)
        db.add_all(inventory_logs)

        # STEP 8: Update Contact Balance (Delegated to ContactsService)
        # In-memory update, no DB call
        balance_change = total_amount - sale_data.paid_amount
        if balance_change > 0:
            ContactsService.update_balance(contact, balance_change)

        # STEP 9: Create Payment Record (if paid)
        if sale_data.paid_amount > 0:
            if not sale_data.payment_method:
                raise ValidationError("Payment method required when paid_amount > 0")

            payment = Payment(
                transaction_id=transaction.id,
                payment_date=sale_data.transaction_date,
                amount=sale_data.paid_amount,
                payment_method=sale_data.payment_method,
                reference_number=sale_data.payment_reference,
                notes=f"Payment for sale {transaction_number}",
            )
            db.add(payment)

        # STEP 10: Flush & Return with Relationships
        # Note: Don't commit here - let FastAPI dependency handle it
        await db.flush()

        # Refresh to load relationships
        await db.refresh(transaction, attribute_names=["contact", "items", "payments"])

        # Eagerly load nested relationships
        for item in transaction.items:
            await db.refresh(item, attribute_names=["product", "container"])

        return transaction

    @staticmethod
    async def create_purchase(
        db: AsyncSession, purchase_data: CreatePurchaseDto
    ) -> Transaction:
        """
        Create a new purchase transaction with inventory addition.
        Uses delegated service methods for clean architecture.

        Business Logic:
        1. Validate contact is supplier or both (delegated)
        2. Validate all products exist (delegated)
        3. Validate all containers exist (delegated)
        4. Create transaction with auto-generated number
        5. Create transaction items
        6. Add inventory to containers
        7. Create inventory logs
        8. Update contact balance (delegated)
        9. Create payment record if paid_amount > 0

        Args:
            db: Database session
            purchase_data: Purchase creation data

        Returns:
            Created transaction with all relationships

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contact/product/container not found
        """

        # STEP 1: Validate Contact (Delegated to ContactsService)
        # Single DB query, returns validated contact
        contact = await ContactsService.validate_for_purchase(
            db, purchase_data.contact_id
        )

        # STEP 2: Validate Products (Delegated to ProductsService)
        # Single batched DB query, returns dict of products
        product_ids = [item.product_id for item in purchase_data.items]
        products_dict = await ProductService.validate_products_exist(db, product_ids)

        # STEP 3: Validate Containers (for destination)
        # Validate container_id provided for all items
        for item in purchase_data.items:
            if not item.container_id:
                raise ValidationError(
                    f"Container ID is required for purchases of product ID {item.product_id}"
                )

        # Get all (product_id, container_id) pairs needed
        # For purchases, we need to check if container-product exists, if not create it
        pairs: List[Tuple[int, int]] = [
            (item.product_id, cast(int, item.container_id))
            for item in purchase_data.items
        ]

        # Batch fetch existing container-products (may not exist for new products)
        container_product_query = select(ContainerProduct).where(
            tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(
                pairs
            )
        )
        cp_result = await db.execute(container_product_query)
        container_products = cp_result.scalars().all()

        # Build lookup map
        container_product_map: Dict[Tuple[int, int], ContainerProduct] = {
            (cp.product_id, cp.container_id): cp for cp in container_products
        }

        # STEP 4: Calculate Totals (Pure logic, no DB calls)
        subtotal = sum(item.quantity * item.unit_price for item in purchase_data.items)
        total_amount = (
            subtotal + purchase_data.tax_amount - purchase_data.discount_amount
        )

        if purchase_data.paid_amount > total_amount:
            raise ValidationError(
                f"Paid amount ({purchase_data.paid_amount}) cannot exceed total ({total_amount})"
            )

        # Determine payment status
        if purchase_data.paid_amount == 0:
            payment_status = PaymentStatus.unpaid
        elif purchase_data.paid_amount >= total_amount:
            payment_status = PaymentStatus.paid
        else:
            payment_status = PaymentStatus.partial

        # STEP 5: Generate Transaction Number (Helper method)
        transaction_number = await TransactionsService._generate_transaction_number(
            db, TransactionType.purchase
        )

        # STEP 6: Create Transaction Record
        transaction = Transaction(
            transaction_number=transaction_number,
            transaction_date=purchase_data.transaction_date,
            type=TransactionType.purchase,
            contact_id=purchase_data.contact_id,
            subtotal=subtotal,
            tax_amount=purchase_data.tax_amount,
            discount_amount=purchase_data.discount_amount,
            total_amount=total_amount,
            paid_amount=purchase_data.paid_amount,
            payment_status=payment_status,
            notes=purchase_data.notes,
        )
        db.add(transaction)
        await db.flush()  # Get transaction.id

        # STEP 7: Create Items & Update Inventory (Bulk operations)
        transaction_items = []
        inventory_logs = []

        for item in purchase_data.items:
            # Create transaction item
            line_total = item.quantity * item.unit_price
            transaction_items.append(
                TransactionItem(
                    transaction_id=transaction.id,
                    product_id=item.product_id,
                    container_id=item.container_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=line_total,
                )
            )

            # Update or create container stock
            assert item.container_id is not None
            key = (item.product_id, item.container_id)
            container_product = container_product_map.get(key)

            if container_product:
                # Existing container-product: add to quantity
                old_qty = container_product.quantity
                container_product.quantity += item.quantity
                new_qty = container_product.quantity
            else:
                # New container-product: create it
                container_product = ContainerProduct(
                    container_id=item.container_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                )
                db.add(container_product)
                old_qty = 0
                new_qty = item.quantity
                # Add to map for potential reuse in same transaction
                container_product_map[key] = container_product

            # Create inventory log
            inventory_logs.append(
                InventoryLog(
                    product_id=item.product_id,
                    container_id=item.container_id,
                    action="purchase",
                    quantity=item.quantity,  # Positive for purchases
                    note=f"Purchase {transaction_number} - {old_qty} → {new_qty}",
                )
            )

        # Bulk insert transaction items and inventory logs
        db.add_all(transaction_items)
        db.add_all(inventory_logs)

        # STEP 8: Update Contact Balance (Delegated to ContactsService)
        # In-memory update, no DB call
        # For purchases: negative balance means we owe the supplier
        balance_change = -(total_amount - purchase_data.paid_amount)
        if balance_change != 0:
            ContactsService.update_balance(contact, balance_change)

        # STEP 9: Create Payment Record (if paid)
        if purchase_data.paid_amount > 0:
            if not purchase_data.payment_method:
                raise ValidationError("Payment method required when paid_amount > 0")

            payment = Payment(
                transaction_id=transaction.id,
                payment_date=purchase_data.transaction_date,
                amount=purchase_data.paid_amount,
                payment_method=purchase_data.payment_method,
                reference_number=purchase_data.payment_reference,
                notes=f"Payment for purchase {transaction_number}",
            )
            db.add(payment)

        # STEP 10: Flush & Return with Relationships
        # Note: Don't commit here - let FastAPI dependency handle it
        await db.flush()

        # Refresh to load relationships
        await db.refresh(transaction, attribute_names=["contact", "items", "payments"])

        # Eagerly load nested relationships
        for item in transaction.items:
            await db.refresh(item, attribute_names=["product", "container"])

        return transaction

    @staticmethod
    async def record_payment(
        db: AsyncSession, transaction_id: int, payment_data: CreatePaymentDto
    ) -> Transaction:
        """
        Record a payment against an existing transaction.
        Updates transaction paid amount, payment status, and contact balance.

        Business Logic:
        1. Validate transaction exists and is not deleted
        2. Calculate remaining balance
        3. Validate payment amount doesn't exceed balance
        4. Create payment record
        5. Update transaction paid_amount and payment_status
        6. Update contact balance

        Args:
            db: Database session
            transaction_id: ID of transaction to add payment to
            payment_data: Payment details

        Returns:
            Updated transaction with all relationships

        Raises:
            NotFoundError: If transaction not found
            ValidationError: If payment invalid (exceeds balance, etc.)
        """

        # STEP 1: Fetch transaction with contact (for balance update)
        # Single query with eager loading
        transaction_query = (
            select(Transaction)
            .options(selectinload(Transaction.contact))
            .where(Transaction.id == transaction_id, Transaction.deleted_at.is_(None))
        )
        result = await db.execute(transaction_query)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise NotFoundError("Transaction", transaction_id)

        # STEP 2: Calculate remaining balance
        remaining_balance = transaction.total_amount - transaction.paid_amount

        if remaining_balance <= 0:
            raise ValidationError(
                f"Transaction {transaction.transaction_number} is already fully paid"
            )

        # STEP 3: Validate payment amount
        if payment_data.amount <= 0:
            raise ValidationError("Payment amount must be greater than zero")

        if payment_data.amount > remaining_balance:
            raise ValidationError(
                f"Payment amount ({payment_data.amount}) exceeds remaining balance ({remaining_balance})"
            )

        # STEP 4: Create payment record
        payment = Payment(
            transaction_id=transaction.id,
            payment_date=payment_data.payment_date,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            reference_number=payment_data.reference_number,
            notes=payment_data.notes,
        )
        db.add(payment)

        # STEP 5: Update transaction paid_amount and payment_status
        transaction.paid_amount += payment_data.amount

        # Recalculate payment status
        if transaction.paid_amount >= transaction.total_amount:
            transaction.payment_status = PaymentStatus.paid
        elif transaction.paid_amount > 0:
            transaction.payment_status = PaymentStatus.partial
        else:
            transaction.payment_status = PaymentStatus.unpaid

        # STEP 6: Update contact balance (Delegated to ContactsService)
        # For sales: reduce balance (customer pays us)
        # For purchases: increase balance (we pay supplier)
        if transaction.type == TransactionType.sale:
            # Customer paying us: reduce their debt
            balance_change = -payment_data.amount
        else:  # purchase
            # We paying supplier: reduce what we owe them
            balance_change = payment_data.amount

        ContactsService.update_balance(transaction.contact, balance_change)

        # STEP 7: Flush changes (let dependency commit)
        await db.flush()

        # STEP 8: Refresh transaction with all relationships
        await db.refresh(transaction, attribute_names=["contact", "items", "payments"])

        # Eagerly load nested relationships
        for item in transaction.items:
            await db.refresh(item, attribute_names=["product", "container"])

        return transaction

    @staticmethod
    async def get_transaction(db: AsyncSession, transaction_id: int) -> Transaction:
        """
        Get a single transaction by ID with all relationships.

        Args:
            db: Database session
            transaction_id: Transaction ID

        Returns:
            Transaction with all relationships

        Raises:
            NotFoundError: If transaction not found or deleted
        """

        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.contact),
                selectinload(Transaction.items).selectinload(TransactionItem.product),
                selectinload(Transaction.items).selectinload(TransactionItem.container),
                selectinload(Transaction.payments),
            )
            .where(Transaction.id == transaction_id, Transaction.deleted_at.is_(None))
        )

        result = await db.execute(query)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise NotFoundError("Transaction", transaction_id)

        return transaction

    @staticmethod
    async def list_transactions(
        db: AsyncSession, filters: Optional[TransactionFilterDto] = None
    ) -> List[Transaction]:
        """
        List transactions with optional filters.
        Returns transactions with all relationships for complete data.

        Args:
            db: Database session
            filters: Optional filter criteria

        Returns:
            List of transactions matching filters
        """
        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.contact),
                selectinload(Transaction.items).selectinload(TransactionItem.product),
                selectinload(Transaction.items).selectinload(TransactionItem.container),
                selectinload(Transaction.payments),
            )
            .where(Transaction.deleted_at.is_(None))
        )

        # Apply filters if provided
        if filters:
            # Filter by transaction type (sale or purchase)
            if filters.type:
                query = query.where(Transaction.type == filters.type)

            # Filter by payment status (paid, partial, unpaid)
            if filters.payment_status:
                query = query.where(
                    Transaction.payment_status == filters.payment_status
                )

            # Filter by contact
            if filters.contact_id:
                query = query.where(Transaction.contact_id == filters.contact_id)

            # Filter by date range
            if filters.from_date:
                query = query.where(Transaction.transaction_date >= filters.from_date)

            if filters.to_date:
                query = query.where(Transaction.transaction_date <= filters.to_date)

            # Search in transaction number or notes
            if filters.search:
                search_pattern = f"%{filters.search}%"
                query = query.where(
                    (Transaction.transaction_number.ilike(search_pattern))
                    | (Transaction.notes.ilike(search_pattern))
                )

        # Order by transaction date descending (newest first)
        query = query.order_by(desc(Transaction.transaction_date), desc(Transaction.id))

        result = await db.execute(query)
        transactions = result.scalars().all()
        return list(transactions)

    @staticmethod
    async def delete_transaction(db: AsyncSession, transaction_id: int) -> None:
        """
        Soft delete a transaction and reverse all its effects.

        Reverses:
        1. Inventory changes (restores quantities)
        2. Contact balance changes
        3. Soft deletes transaction, items, and payments

        Args:
            db: Database session
            transaction_id: Transaction ID to delete

        Raises:
            NotFoundError: If transaction not found or already deleted
        """
        from datetime import datetime

        # STEP 1: Fetch transaction with all relationships
        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.contact),
                selectinload(Transaction.items),
                selectinload(Transaction.payments),
            )
            .where(Transaction.id == transaction_id, Transaction.deleted_at.is_(None))
        )

        result = await db.execute(query)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise NotFoundError("Transaction", transaction_id)

        # STEP 2: Reverse inventory changes
        # Fetch all affected container-products
        if transaction.items:
            pairs = [
                (item.product_id, item.container_id)
                for item in transaction.items
                if item.container_id
            ]

            if pairs:
                container_product_query = select(ContainerProduct).where(
                    tuple_(
                        ContainerProduct.product_id, ContainerProduct.container_id
                    ).in_(pairs)
                )
                cp_result = await db.execute(container_product_query)
                container_products = cp_result.scalars().all()

                container_product_map = {
                    (cp.product_id, cp.container_id): cp for cp in container_products
                }

                # Reverse inventory for each item
                for item in transaction.items:
                    if not item.container_id:
                        continue

                    key = (item.product_id, item.container_id)
                    container_product = container_product_map.get(key)

                    if container_product:
                        if transaction.type == TransactionType.sale:
                            # Restore quantity (was deducted)
                            container_product.quantity += item.quantity
                        else:  # purchase
                            # Deduct quantity (was added)
                            container_product.quantity -= item.quantity

        # STEP 3: Reverse contact balance
        # Calculate the balance that was added to the contact
        balance_to_reverse = transaction.total_amount - transaction.paid_amount

        if balance_to_reverse > 0:
            if transaction.type == TransactionType.sale:
                # Reverse customer receivable
                ContactsService.update_balance(transaction.contact, -balance_to_reverse)
            else:  # purchase
                # Reverse supplier payable
                ContactsService.update_balance(transaction.contact, balance_to_reverse)

        # STEP 4: Soft delete transaction and related records
        now = datetime.utcnow()
        transaction.deleted_at = now

        # Soft delete all transaction items
        for item in transaction.items:
            item.deleted_at = now

        # Soft delete all payments
        for payment in transaction.payments:
            payment.deleted_at = now

        # STEP 5: Flush changes (let dependency commit)
        await db.flush()
