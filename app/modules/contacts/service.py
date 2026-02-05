"""
ContactsService - Business logic for contacts management.
Optimized queries with no extra SQL calls.
"""

from typing import List, Optional
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError, ValidationError
from .models import Contact, ContactType
from .schemas import CreateContactDto, UpdateContactDto, FilterContactsDto


class ContactsService:
    """
    Contacts service with optimized database queries.
    All methods use run_db() for thread-safe Turso operations.
    """

    @staticmethod
    async def create(create_dto: CreateContactDto) -> Contact:
        """
        Create a new contact.
        Optimized: Single INSERT query.

        Args:
            create_dto: DTO containing contact information

        Returns:
            Created contact entity
        """
        def _create(db: Session) -> Contact:
            contact = Contact(**create_dto.model_dump())
            db.add(contact)
            db.flush()
            db.refresh(contact)
            return contact
        return await run_db(_create)

    @staticmethod
    async def find_all(filters: Optional[FilterContactsDto] = None) -> List[Contact]:
        """
        Find all contacts with optional filters.
        Optimized: Single SELECT query with dynamic filters.

        Args:
            filters: Optional DTO containing filter criteria
        """
        def _find_all(db: Session) -> List[Contact]:
            query = select(Contact).where(Contact.deleted_at.is_(None))

            if filters:
                # Apply type filter
                if filters.types:
                    query = query.where(Contact.type.in_(filters.types))

                # Apply balance filter
                if filters.balance == "positive":
                    query = query.where(Contact.balance > 0)
                elif filters.balance == "negative":
                    query = query.where(Contact.balance < 0)

                # Apply search filter
                if filters.search:
                    query = query.where(
                        Contact.name.ilike(f"%{filters.search}%")
                        | Contact.phone.ilike(f"%{filters.search}%")
                    )

            result = db.execute(query)
            contacts = result.scalars().all()
            return list(contacts)
        return await run_db(_find_all)

    @staticmethod
    async def find_one(contact_id: int) -> Contact:
        """
        Find a single contact by id where deleted_at is null.
        Optimized: Single SELECT with composite WHERE clause.

        Raises:
            NotFoundError: If contact not found or is soft-deleted
        """
        def _find_one(db: Session) -> Contact:
            result = db.execute(
                select(Contact).where(
                    Contact.id == contact_id, Contact.deleted_at.is_(None)
                )
            )
            contact = result.scalar_one_or_none()

            if not contact:
                raise NotFoundError("Contact", contact_id)

            return contact
        return await run_db(_find_one)

    @staticmethod
    async def update(contact_id: int, update_dto: UpdateContactDto) -> Contact:
        """
        Update contact information.
        Optimized: Single UPDATE query, only updates non-None fields.

        Args:
            contact_id: ID of contact to update
            update_dto: DTO containing fields to update

        Returns:
            Updated contact entity

        Raises:
            NotFoundError: If contact not found or is soft-deleted
        """
        def _update(db: Session) -> Contact:
            # Build update dict with only provided values
            update_data = update_dto.model_dump(exclude_unset=True)

            # Single SELECT + UPDATE query
            result = db.execute(
                select(Contact).where(
                    Contact.id == contact_id, Contact.deleted_at.is_(None)
                )
            )
            contact = result.scalar_one_or_none()

            if not contact:
                raise NotFoundError("Contact", contact_id)

            if update_data:
                for key, value in update_data.items():
                    setattr(contact, key, value)

                db.flush()
                db.refresh(contact)
            
            return contact
        return await run_db(_update)

    @staticmethod
    async def remove(contact_id: int) -> None:
        """
        Soft delete a contact by setting deleted_at timestamp.
        Optimized: Single UPDATE query.

        Args:
            contact_id: ID of contact to soft delete

        Raises:
            NotFoundError: If contact not found or already deleted
        """
        def _remove(db: Session) -> None:
            from datetime import datetime

            result = db.execute(
                select(Contact).where(
                    Contact.id == contact_id, Contact.deleted_at.is_(None)
                )
            )
            contact = result.scalar_one_or_none()

            if not contact:
                raise NotFoundError("Contact", contact_id)

            contact.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)

    @staticmethod
    async def validate_for_sale(contact_id: int) -> Contact:
        """
        Validate that a contact exists and can be used for sales.
        
        Args:
            contact_id: Contact ID to validate
            
        Returns:
            Contact entity if valid
            
        Raises:
            NotFoundError: If contact not found
            ValidationError: If contact is not a customer or both
        """
        def _validate(db: Session) -> Contact:
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
        return await run_db(_validate)

    @staticmethod
    async def validate_for_purchase(contact_id: int) -> Contact:
        """
        Validate that a contact exists and can be used for purchases.
        
        Args:
            contact_id: Contact ID to validate
            
        Returns:
            Contact entity if valid
            
        Raises:
            NotFoundError: If contact not found
            ValidationError: If contact is not a supplier or both
        """
        def _validate(db: Session) -> Contact:
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
        return await run_db(_validate)

    @staticmethod
    def update_balance(contact: Contact, amount: Decimal) -> None:
        """
        Update contact balance (in-memory, no DB call).
        Note: This is called within a run_db() context.
        
        Args:
            contact: Pre-fetched contact entity
            amount: Amount to add to balance (positive for receivables, negative for payables)
        """
        contact.balance += amount
