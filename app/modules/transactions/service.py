"""
TransactionsService - Business logic for sales and purchase transactions.
Handles inventory updates, payment tracking, and contact balance management.
"""

from typing import List, Optional, Dict, Tuple, cast, Union
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, desc, tuple_
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from app.core.exceptions import ValidationError, NotFoundError
from .models import (
    Transaction,
    TransactionItem,
    TransactionType,
    PaymentStatus,
)
from app.modules.payments.models import Payment, PaymentMethod
from .schemas import (
    CreateSaleDto,
    CreatePurchaseDto,
    CreatePaymentDto,
    TransactionFilterDto,
)
from app.modules.contacts.models import Contact, ContactType
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog


# Import invoice service for background invoice generation
from .invoice_service import InvoiceService


class TransactionsService:
    """
    Transactions service for managing sales and purchases.
    Handles complex business logic with proper locking and audit trails.
    All methods use run_db() for thread-safe Turso operations.
    """

    # --- Internal sync helper methods (called within run_db context) ---
    
    @staticmethod
    def _validate_contact_for_sale(db: Session, contact_id: int) -> Contact:
        """Validate that a contact exists and can be used for sales."""
        contact_query = select(Contact).where(
            Contact.id == contact_id,
            Contact.deleted_at.is_(None)
        )
        result = db.execute(contact_query)
        contact = result.scalar_one_or_none()

        if not contact:
            raise NotFoundError("Contact", contact_id)

        if contact.type not in [ContactType.customer, ContactType.both]:
            raise ValidationError(
                f"Contact '{contact.name}' is not a customer. "
                f"Only customers or mixed contacts can be used for sales."
            )

        return contact

    @staticmethod
    def _validate_contact_for_purchase(db: Session, contact_id: int) -> Contact:
        """Validate that a contact exists and can be used for purchases."""
        contact_query = select(Contact).where(
            Contact.id == contact_id,
            Contact.deleted_at.is_(None)
        )
        result = db.execute(contact_query)
        contact = result.scalar_one_or_none()

        if not contact:
            raise NotFoundError("Contact", contact_id)

        if contact.type not in [ContactType.supplier, ContactType.both]:
            raise ValidationError(
                f"Contact '{contact.name}' is not a supplier. "
                f"Only suppliers or mixed contacts can be used for purchases."
            )

        return contact

    @staticmethod
    def _validate_products_exist(db: Session, product_ids: List[int]) -> Dict[int, Product]:
        """Validate that all products exist and return them as a dict."""
        if not product_ids:
            return {}
            
        products_query = select(Product).where(
            Product.id.in_(product_ids),
            Product.deleted_at.is_(None)
        )
        products_result = db.execute(products_query)
        products = products_result.scalars().all()

        if len(products) != len(set(product_ids)):
            found_ids = {p.id for p in products}
            missing_ids = set(product_ids) - found_ids
            raise NotFoundError("Products", list(missing_ids))

        return {p.id: p for p in products}

    @staticmethod
    def _validate_and_get_stock(
        db: Session, items: List[Tuple[int, int]]
    ) -> Dict[Tuple[int, int], ContainerProduct]:
        """Validate stock availability for multiple product-container pairs."""
        if not items:
            return {}
            
        container_product_query = select(ContainerProduct).where(
            tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(items)
        )
        cp_result = db.execute(container_product_query)
        container_products = cp_result.scalars().all()
        
        container_product_map = {
            (cp.product_id, cp.container_id): cp for cp in container_products
        }
        
        if len(container_product_map) != len(set(items)):
            found_keys = set(container_product_map.keys())
            missing_keys = set(items) - found_keys
            raise ValidationError(
                f"Products not found in specified containers: {list(missing_keys)}"
            )
        
        return container_product_map

    @staticmethod
    def _update_contact_balance(contact: Contact, amount: Decimal) -> None:
        """Update contact balance (in-memory, no DB call)."""
        contact.balance += amount

    @staticmethod
    def _generate_transaction_number(db: Session, transaction_type: TransactionType) -> str:
        """
        Generate unique transaction number based on type.
        Format: SALE-0001, SALE-0002 or PUR-0001, PUR-0002
        """
        prefix = "SALE" if transaction_type == TransactionType.sale else "PUR"

        query = (
            select(Transaction)
            .where(Transaction.type == transaction_type)
            .order_by(desc(Transaction.id))
            .limit(1)
        )

        result = db.execute(query)
        last_transaction = result.scalar_one_or_none()

        if not last_transaction:
            return f"{prefix}-0001"

        try:
            last_number = int(last_transaction.transaction_number.split("-")[1])
            new_number = last_number + 1
            return f"{prefix}-{new_number:04d}"
        except (IndexError, ValueError):
            return f"{prefix}-0001"

    # --- Public async methods ---

    @staticmethod
    async def create_sale(sale_data: CreateSaleDto) -> Transaction:
        """
        Create a new sale transaction with inventory deduction.

        Args:
            sale_data: Sale creation data

        Returns:
            Created transaction with all relationships

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contact/product/container not found
        """
        def _create_sale(db: Session) -> Transaction:
            return TransactionsService._create_transaction(
                db, TransactionType.sale, sale_data
            )
        return await run_db(_create_sale)

    @staticmethod
    async def create_purchase(purchase_data: CreatePurchaseDto) -> Transaction:
        """
        Create a new purchase transaction with inventory addition.

        Args:
            purchase_data: Purchase creation data

        Returns:
            Created transaction with all relationships

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contact/product/container not found
        """
        def _create_purchase(db: Session) -> Transaction:
            return TransactionsService._create_transaction(
                db, TransactionType.purchase, purchase_data
            )
        return await run_db(_create_purchase)

    @staticmethod
    def _create_transaction(
        db: Session,
        transaction_type: TransactionType,
        transaction_data: Union[CreateSaleDto, CreatePurchaseDto],
    ) -> Transaction:
        """
        Unified transaction creation for both sales and purchases.
        Uses delegated service methods for clean architecture.

        Business Logic:
        1. Validate contact (customer for sale, supplier for purchase)
        2. Validate all products exist
        3. Validate/manage container stock
        4. Create transaction with auto-generated number
        5. Create transaction items
        6. Update inventory (decrease for sale, increase for purchase)
        7. Create inventory logs
        8. Update contact balance
        9. Create payment record if paid_amount > 0
        """
        is_sale = transaction_type == TransactionType.sale

        # STEP 1: Validate Contact
        if is_sale:
            contact = TransactionsService._validate_contact_for_sale(db, transaction_data.contact_id)
        else:
            contact = TransactionsService._validate_contact_for_purchase(db, transaction_data.contact_id)

        # STEP 2: Validate Products
        product_ids = [item.product_id for item in transaction_data.items]
        products_dict = TransactionsService._validate_products_exist(db, product_ids)

        # STEP 3: Validate Container Stock
        for item in transaction_data.items:
            if not item.container_id:
                raise ValidationError(
                    f"Container ID is required for {transaction_type.value}s of product ID {item.product_id}"
                )

        pairs: List[Tuple[int, int]] = [
            (item.product_id, cast(int, item.container_id))
            for item in transaction_data.items
        ]

        if is_sale:
            container_product_map = TransactionsService._validate_and_get_stock(db, pairs)
            
            for item in transaction_data.items:
                assert item.container_id is not None
                key = (item.product_id, item.container_id)
                container_product = container_product_map[key]

                if container_product.quantity < item.quantity:
                    product_name = products_dict[item.product_id].name
                    raise ValidationError(
                        f"Insufficient stock for '{product_name}'. "
                        f"Available: {container_product.quantity}, Required: {item.quantity}"
                    )
        else:
            container_product_query = select(ContainerProduct).where(
                tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(pairs)
            )
            cp_result = db.execute(container_product_query)
            container_products = cp_result.scalars().all()
            container_product_map: Dict[Tuple[int, int], ContainerProduct] = {
                (cp.product_id, cp.container_id): cp for cp in container_products
            }

        # STEP 4: Calculate Totals
        subtotal = sum(item.quantity * item.unit_price for item in transaction_data.items)
        total_amount = subtotal + transaction_data.tax_amount - transaction_data.discount_amount

        if transaction_data.paid_amount > total_amount:
            raise ValidationError(
                f"Paid amount ({transaction_data.paid_amount}) cannot exceed total ({total_amount})"
            )

        if transaction_data.paid_amount == 0:
            payment_status = PaymentStatus.unpaid
        elif transaction_data.paid_amount >= total_amount:
            payment_status = PaymentStatus.paid
        else:
            payment_status = PaymentStatus.partial

        # STEP 5: Generate Transaction Number
        transaction_number = TransactionsService._generate_transaction_number(
            db, transaction_type
        )

        # STEP 6: Create Transaction Record
        transaction = Transaction(
            transaction_number=transaction_number,
            transaction_date=transaction_data.transaction_date,
            type=transaction_type,
            contact_id=transaction_data.contact_id,
            subtotal=subtotal,
            tax_amount=transaction_data.tax_amount,
            discount_amount=transaction_data.discount_amount,
            total_amount=total_amount,
            paid_amount=transaction_data.paid_amount,
            payment_status=payment_status,
            notes=transaction_data.notes,
        )
        db.add(transaction)
        db.flush()

        # STEP 7: Create Items & Update Inventory
        transaction_items = []
        inventory_logs = []

        for item in transaction_data.items:
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

            assert item.container_id is not None
            key = (item.product_id, item.container_id)

            if is_sale:
                container_product = container_product_map[key]
                old_qty = container_product.quantity
                container_product.quantity -= item.quantity
                new_qty = container_product.quantity
                inventory_quantity = -item.quantity
                action = "sale"
            else:
                container_product = container_product_map.get(key)
                if container_product:
                    old_qty = container_product.quantity
                    container_product.quantity += item.quantity
                    new_qty = container_product.quantity
                else:
                    container_product = ContainerProduct(
                        container_id=item.container_id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )
                    db.add(container_product)
                    old_qty = 0
                    new_qty = item.quantity
                    container_product_map[key] = container_product
                inventory_quantity = item.quantity
                action = "purchase"

            inventory_logs.append(
                InventoryLog(
                    product_id=item.product_id,
                    container_id=item.container_id,
                    action=action,
                    quantity=inventory_quantity,
                    note=f"{action.capitalize()} {transaction_number} - {old_qty} → {new_qty}",
                )
            )

        db.add_all(transaction_items)
        db.add_all(inventory_logs)

        # STEP 8: Update Contact Balance
        outstanding_amount = total_amount - transaction_data.paid_amount
        balance_change = outstanding_amount if is_sale else -outstanding_amount
        
        if balance_change != 0:
            TransactionsService._update_contact_balance(contact, balance_change)

        # STEP 9: Create Payment Record (if paid)
        if transaction_data.paid_amount > 0:
            if not transaction_data.payment_method:
                raise ValidationError("Payment method required when paid_amount > 0")

            payment = Payment(
                transaction_id=transaction.id,
                payment_date=transaction_data.transaction_date,
                amount=transaction_data.paid_amount,
                payment_method=transaction_data.payment_method,
                reference_number=transaction_data.payment_reference,
                notes=f"Payment for {transaction_type.value} {transaction_number}",
            )
            db.add(payment)

        # STEP 10: Flush & Refresh
        db.flush()
        db.refresh(transaction)

        # Note: Invoice generation is skipped as it requires async operations
        # Can be handled separately after the transaction

        return transaction

    @staticmethod
    async def record_payment(transaction_id: int, payment_data: CreatePaymentDto) -> Transaction:
        """
        Record a payment against an existing transaction.
        Updates transaction paid amount, payment status, and contact balance.
        """
        def _record_payment(db: Session) -> Transaction:
            # STEP 1: Fetch transaction with contact
            transaction_query = (
                select(Transaction)
                .options(selectinload(Transaction.contact))
                .where(Transaction.id == transaction_id, Transaction.deleted_at.is_(None))
            )
            result = db.execute(transaction_query)
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

            if transaction.paid_amount >= transaction.total_amount:
                transaction.payment_status = PaymentStatus.paid
            elif transaction.paid_amount > 0:
                transaction.payment_status = PaymentStatus.partial
            else:
                transaction.payment_status = PaymentStatus.unpaid

            # STEP 6: Update contact balance
            if transaction.type == TransactionType.sale:
                balance_change = -payment_data.amount
            else:
                balance_change = payment_data.amount

            TransactionsService._update_contact_balance(transaction.contact, balance_change)

            # STEP 7: Flush and refresh
            db.flush()
            db.refresh(transaction)

            return transaction
        return await run_db(_record_payment)

    @staticmethod
    async def get_transaction(transaction_id: int) -> Transaction:
        """
        Get a single transaction by ID with all relationships.
        """
        def _get_transaction(db: Session) -> Transaction:
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

            result = db.execute(query)
            transaction = result.scalar_one_or_none()

            if not transaction:
                raise NotFoundError("Transaction", transaction_id)

            return transaction
        return await run_db(_get_transaction)

    @staticmethod
    async def list_transactions(filters: Optional[TransactionFilterDto] = None) -> List[Transaction]:
        """
        List transactions with optional filters.
        """
        def _list_transactions(db: Session) -> List[Transaction]:
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

            if filters:
                if filters.type:
                    query = query.where(Transaction.type == filters.type)
                if filters.payment_status:
                    query = query.where(Transaction.payment_status == filters.payment_status)
                if filters.contact_id:
                    query = query.where(Transaction.contact_id == filters.contact_id)
                if filters.from_date:
                    query = query.where(Transaction.transaction_date >= filters.from_date)
                if filters.to_date:
                    query = query.where(Transaction.transaction_date <= filters.to_date)
                if filters.search:
                    search_pattern = f"%{filters.search}%"
                    query = query.where(
                        (Transaction.transaction_number.ilike(search_pattern))
                        | (Transaction.notes.ilike(search_pattern))
                    )

            query = query.order_by(desc(Transaction.transaction_date), desc(Transaction.id))

            result = db.execute(query)
            transactions = result.scalars().all()
            return list(transactions)
        return await run_db(_list_transactions)

    @staticmethod
    async def delete_transaction(transaction_id: int) -> None:
        """
        Soft delete a transaction and reverse all its effects.
        """
        def _delete_transaction(db: Session) -> None:
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

            result = db.execute(query)
            transaction = result.scalar_one_or_none()

            if not transaction:
                raise NotFoundError("Transaction", transaction_id)

            # STEP 2: Reverse inventory changes
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
                    cp_result = db.execute(container_product_query)
                    container_products = cp_result.scalars().all()

                    container_product_map = {
                        (cp.product_id, cp.container_id): cp for cp in container_products
                    }

                    for item in transaction.items:
                        if not item.container_id:
                            continue

                        key = (item.product_id, item.container_id)
                        container_product = container_product_map.get(key)

                        if container_product:
                            if transaction.type == TransactionType.sale:
                                container_product.quantity += item.quantity
                            else:
                                container_product.quantity -= item.quantity

            # STEP 3: Reverse contact balance
            balance_to_reverse = transaction.total_amount - transaction.paid_amount

            if balance_to_reverse > 0:
                if transaction.type == TransactionType.sale:
                    TransactionsService._update_contact_balance(transaction.contact, -balance_to_reverse)
                else:
                    TransactionsService._update_contact_balance(transaction.contact, balance_to_reverse)

            # STEP 4: Soft delete transaction and related records
            now = datetime.utcnow()
            transaction.deleted_at = now

            for item in transaction.items:
                item.deleted_at = now

            for payment in transaction.payments:
                payment.deleted_at = now

            db.flush()
        await run_db(_delete_transaction)
