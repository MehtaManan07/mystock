"""
TransactionsService - Business logic for sales and purchase transactions.
Handles inventory updates, payment tracking, and contact balance management.
"""

from typing import List, Optional, Dict, Tuple, cast, Union
from datetime import date
from decimal import Decimal
import math
from sqlalchemy import select, func, desc, tuple_, insert as sa_insert, update as sa_update, case as sa_case
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from app.core.exceptions import ValidationError, NotFoundError
from .models import (
    Transaction,
    TransactionItem,
    TransactionType,
    PaymentStatus,
    TaxType,
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
from app.modules.settings.models import CompanySettings
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
            tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(items),
            ContainerProduct.deleted_at.is_(None),
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
    def _determine_tax_type(db: Session, contact: Contact, explicit_tax_type: Optional[TaxType] = None) -> TaxType:
        """
        Determine tax type (IGST vs CGST+SGST) for a transaction.

        Rules:
        - If explicitly provided by user -> use it
        - If contact has GSTIN -> compare state codes with seller GSTIN
        - If contact has no GSTIN and no explicit choice -> default to cgst_sgst (assume same state)
        """
        if explicit_tax_type is not None:
            return explicit_tax_type

        # Get seller GSTIN from company settings
        settings = db.execute(
            select(CompanySettings).where(CompanySettings.is_active == True)
        ).scalar_one_or_none()

        seller_state = settings.seller_gstin[:2] if settings and settings.seller_gstin and len(settings.seller_gstin) >= 2 else None

        if contact.gstin and len(contact.gstin) >= 2:
            buyer_state = contact.gstin[:2]
            if seller_state and seller_state == buyer_state:
                return TaxType.cgst_sgst
            return TaxType.igst

        # No GSTIN on contact - default to intra-state (same state assumption)
        return TaxType.cgst_sgst

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
        last_transaction = result.unique().scalar_one_or_none()

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

        # STEP 1b: Determine tax type
        tax_type = TransactionsService._determine_tax_type(
            db, contact, transaction_data.tax_type
        )

        # STEP 2: Validate Products
        product_ids = [item.product_id for item in transaction_data.items]
        products_dict = TransactionsService._validate_products_exist(db, product_ids)

        # STEP 3: Validate Container IDs are present
        for item in transaction_data.items:
            if not item.container_id:
                raise ValidationError(
                    f"Container ID is required for {transaction_type.value}s of product ID {item.product_id}"
                )

        pairs: List[Tuple[int, int]] = [
            (item.product_id, cast(int, item.container_id))
            for item in transaction_data.items
        ]

        # STEP 3a: Fetch + validate ContainerProducts
        if is_sale:
            container_product_map = TransactionsService._validate_and_get_stock(db, pairs)

            for item in transaction_data.items:
                assert item.container_id is not None
                cp = container_product_map[(item.product_id, item.container_id)]
                product = products_dict[item.product_id]
                if cp.quantity < item.quantity:
                    raise ValidationError(
                        f"Insufficient stock for '{product.name}'. "
                        f"Available: {cp.quantity} items, Required: {item.quantity} items"
                    )
        else:
            cp_result = db.execute(
                select(ContainerProduct).where(
                    tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(pairs)
                )
            )
            container_product_map: Dict[Tuple[int, int], ContainerProduct] = {
                (cp.product_id, cp.container_id): cp for cp in cp_result.scalars().all()
            }

        # STEP 4: Calculate Totals
        subtotal = sum(item.quantity * item.unit_price for item in transaction_data.items)
        total_before_rounding = subtotal + transaction_data.tax_amount - transaction_data.discount_amount
        total_amount = Decimal(math.ceil(float(total_before_rounding)))

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
            product_details_display_mode=transaction_data.product_details_display_mode,
            tax_type=tax_type,
        )
        db.add(transaction)
        db.flush()  # Needed to get transaction.id for FK references below

        # STEP 7: Build item/log dicts + compute ContainerProduct deltas in one pass
        action = "sale" if is_sale else "purchase"
        item_dicts: List[dict] = []
        log_dicts: List[dict] = []
        # Tracks running quantity for accurate log notes when same pair appears >1 time
        running_qty: Dict[Tuple[int, int], int] = {
            key: cp.quantity for key, cp in container_product_map.items()
        }
        # Accumulated quantity deltas per (product_id, container_id) for bulk UPDATE
        cp_update_deltas: Dict[Tuple[int, int], int] = {}
        # New (product_id, container_id) pairs that need INSERT instead of UPDATE (purchase only)
        new_cp_dicts: Dict[Tuple[int, int], int] = {}

        for item in transaction_data.items:
            assert item.container_id is not None
            key = (item.product_id, item.container_id)
            delta = -item.quantity if is_sale else item.quantity

            old_qty = running_qty.get(key, 0)
            new_qty = old_qty + delta
            running_qty[key] = new_qty

            if is_sale or key in container_product_map:
                # Existing row — accumulate delta for bulk UPDATE
                cp_update_deltas[key] = cp_update_deltas.get(key, 0) + delta
            else:
                # Purchase only: new product+container pair — accumulate for bulk INSERT
                new_cp_dicts[key] = new_cp_dicts.get(key, 0) + delta

            item_dicts.append({
                "transaction_id": transaction.id,
                "product_id": item.product_id,
                "container_id": item.container_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": item.quantity * item.unit_price,
            })
            log_dicts.append({
                "product_id": item.product_id,
                "container_id": item.container_id,
                "action": action,
                "quantity": delta,
                "note": f"{action.capitalize()} {transaction_number} - {old_qty} → {new_qty}",
            })

        # STEP 8: Bulk INSERT TransactionItems — 1 statement instead of N
        db.execute(sa_insert(TransactionItem), item_dicts)

        # STEP 9: Bulk INSERT InventoryLogs — 1 statement instead of N
        db.execute(sa_insert(InventoryLog), log_dicts)

        # STEP 10: Bulk UPDATE ContainerProduct quantities — 1 CASE WHEN instead of N UPDATEs
        # Also clears deleted_at to restore soft-deleted rows when stock arrives via purchases.
        # For sales, _validate_and_get_stock already ensures only active rows are used.
        if cp_update_deltas:
            db.execute(
                sa_update(ContainerProduct)
                .where(
                    tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(
                        list(cp_update_deltas.keys())
                    )
                )
                .values(
                    quantity=sa_case(
                        *[
                            (
                                (ContainerProduct.product_id == pid) & (ContainerProduct.container_id == cid),
                                ContainerProduct.quantity + delta,
                            )
                            for (pid, cid), delta in cp_update_deltas.items()
                        ],
                        else_=ContainerProduct.quantity,
                    ),
                    deleted_at=None,
                )
            )

        # Purchase only: INSERT new ContainerProduct rows for brand-new product+container pairs
        if new_cp_dicts:
            db.execute(
                sa_insert(ContainerProduct),
                [
                    {"product_id": pid, "container_id": cid, "quantity": qty}
                    for (pid, cid), qty in new_cp_dicts.items()
                ],
            )

        # STEP 11: Update Contact Balance
        outstanding_amount = total_amount - transaction_data.paid_amount
        balance_change = outstanding_amount if is_sale else -outstanding_amount
        if balance_change != 0:
            TransactionsService._update_contact_balance(contact, balance_change)

        # STEP 12: Create Payment Record (if paid)
        payment: Optional[Payment] = None
        if transaction_data.paid_amount > 0:
            if not transaction_data.payment_method:
                raise ValidationError("Payment method required when paid_amount > 0")

            payment_type = 'income' if transaction_type == TransactionType.sale else 'expense'
            payment = Payment(
                transaction_id=transaction.id,
                payment_date=transaction_data.transaction_date,
                amount=transaction_data.paid_amount,
                payment_method=transaction_data.payment_method,
                reference_number=transaction_data.payment_reference,
                description=f"Payment for {transaction_type.value} {transaction_number}",
                type=payment_type,
                category="transaction_payment",
            )
            db.add(payment)

        # STEP 13: Flush ORM-tracked mutations (contact balance + payment INSERT)
        db.flush()

        # STEP 14: Load items with product+container via a single JOIN SELECT.
        # Replaces db.refresh(transaction) which was firing a redundant round-trip.
        loaded_items = list(
            db.execute(
                select(TransactionItem)
                .where(
                    TransactionItem.transaction_id == transaction.id,
                    TransactionItem.deleted_at.is_(None),
                )
                .options(
                    selectinload(TransactionItem.product),
                    selectinload(TransactionItem.container),
                )
            ).scalars().all()
        )

        # Populate relationships from in-memory objects — no extra DB round-trips
        transaction.items = loaded_items
        transaction.contact = contact
        transaction.payments = [payment] if payment else []

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
            transaction = result.unique().scalar_one_or_none()

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
            # Derive payment type from transaction type
            payment_type = 'income' if transaction.type == TransactionType.sale else 'expense'

            payment = Payment(
                transaction_id=transaction.id,
                payment_date=payment_data.payment_date,
                amount=payment_data.amount,
                payment_method=payment_data.payment_method,
                reference_number=payment_data.reference_number,
                description=payment_data.notes,  # Payment model uses 'description', not 'notes'
                type=payment_type,
                category="transaction_payment",
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
            transaction = result.unique().scalar_one_or_none()

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

            # STEP 1: Fetch transaction — only load items+contact (payments not needed in memory)
            query = (
                select(Transaction)
                .options(
                    selectinload(Transaction.contact),
                    selectinload(Transaction.items),
                )
                .where(Transaction.id == transaction_id, Transaction.deleted_at.is_(None))
            )

            result = db.execute(query)
            transaction = result.unique().scalar_one_or_none()

            if not transaction:
                raise NotFoundError("Transaction", transaction_id)

            # STEP 2: Reverse inventory — bulk CASE WHEN UPDATE (1 statement instead of N)
            if transaction.items:
                pairs = [
                    (item.product_id, item.container_id)
                    for item in transaction.items
                    if item.container_id
                ]

                if pairs:
                    cp_result = db.execute(
                        select(ContainerProduct).where(
                            tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(pairs)
                        )
                    )
                    container_product_map = {
                        (cp.product_id, cp.container_id): cp
                        for cp in cp_result.scalars().all()
                    }

                    # Accumulate per-key deltas (reverse of original: add back for sales, subtract for purchases)
                    cp_deltas: Dict[Tuple[int, int], int] = {}
                    for item in transaction.items:
                        if not item.container_id:
                            continue
                        key = (item.product_id, item.container_id)
                        if key not in container_product_map:
                            continue
                        delta = item.quantity if transaction.type == TransactionType.sale else -item.quantity
                        cp_deltas[key] = cp_deltas.get(key, 0) + delta

                    if cp_deltas:
                        db.execute(
                            sa_update(ContainerProduct)
                            .where(
                                tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(
                                    list(cp_deltas.keys())
                                )
                            )
                            .values(
                                quantity=sa_case(
                                    *[
                                        (
                                            (ContainerProduct.product_id == pid) & (ContainerProduct.container_id == cid),
                                            ContainerProduct.quantity + delta,
                                        )
                                        for (pid, cid), delta in cp_deltas.items()
                                    ],
                                    else_=ContainerProduct.quantity,
                                )
                            )
                        )

            # STEP 3: Reverse contact balance
            balance_to_reverse = transaction.total_amount - transaction.paid_amount
            if balance_to_reverse > 0:
                if transaction.type == TransactionType.sale:
                    TransactionsService._update_contact_balance(transaction.contact, -balance_to_reverse)
                else:
                    TransactionsService._update_contact_balance(transaction.contact, balance_to_reverse)

            # STEP 4: Soft delete — transaction via ORM, items+payments via bulk UPDATE
            now = datetime.utcnow()
            transaction.deleted_at = now

            # Single UPDATE for all items instead of N individual ORM mutations
            if transaction.items:
                db.execute(
                    sa_update(TransactionItem)
                    .where(
                        TransactionItem.transaction_id == transaction_id,
                        TransactionItem.deleted_at.is_(None),
                    )
                    .values(deleted_at=now)
                )

            # Single UPDATE for all payments instead of M individual ORM mutations
            db.execute(
                sa_update(Payment)
                .where(
                    Payment.transaction_id == transaction_id,
                    Payment.deleted_at.is_(None),
                )
                .values(deleted_at=now)
            )

            db.flush()
        await run_db(_delete_transaction)
