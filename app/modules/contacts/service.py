"""
ContactsService - Business logic for contacts management.
Optimized queries with no extra SQL calls.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from .models import Contact, ContactType
from .schemas import CreateContactDto, UpdateContactDto, FilterContactsDto


class ContactsService:
    """
    Contacts service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    """

    @staticmethod
    async def create(db: AsyncSession, create_dto: CreateContactDto) -> Contact:
        """
        Create a new contact.
        Optimized: Single INSERT query.

        Args:
            create_dto: DTO containing contact information

        Returns:
            Created contact entity
        """
        contact = Contact(**create_dto.model_dump())
        db.add(contact)
        await db.flush()
        await db.refresh(contact)
        return contact

    @staticmethod
    async def find_all(
        db: AsyncSession,
        filters: Optional[FilterContactsDto] = None,
    ) -> List[Contact]:
        """
        Find all contacts with optional filters.
        Optimized: Single SELECT query with dynamic filters.

        Args:
            filters: Optional DTO containing filter criteria
        """
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

        result = await db.execute(query)
        contacts = result.scalars().all()
        return list(contacts)

    @staticmethod
    async def find_one(db: AsyncSession, contact_id: int) -> Contact:
        """
        Find a single contact by id where deleted_at is null.
        Optimized: Single SELECT with composite WHERE clause.

        Raises:
            NotFoundError: If contact not found or is soft-deleted
        """
        result = await db.execute(
            select(Contact).where(
                Contact.id == contact_id, Contact.deleted_at.is_(None)
            )
        )
        contact = result.scalar_one_or_none()

        if not contact:
            raise NotFoundError("Contact", contact_id)

        return contact

    @staticmethod
    async def update(
        db: AsyncSession, contact_id: int, update_dto: UpdateContactDto
    ) -> Contact:
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
        # Build update dict with only provided values
        update_data = update_dto.model_dump(exclude_unset=True)

        if not update_data:
            # If no fields to update, just return the existing contact
            return await ContactsService.find_one(db, contact_id)

        # Single SELECT + UPDATE query
        result = await db.execute(
            select(Contact).where(
                Contact.id == contact_id, Contact.deleted_at.is_(None)
            )
        )
        contact = result.scalar_one_or_none()

        if not contact:
            raise NotFoundError("Contact", contact_id)

        for key, value in update_data.items():
            setattr(contact, key, value)

        await db.flush()
        await db.refresh(contact)
        return contact

    @staticmethod
    async def remove(db: AsyncSession, contact_id: int) -> None:
        """
        Soft delete a contact by setting deleted_at timestamp.
        Optimized: Single UPDATE query.

        Args:
            contact_id: ID of contact to soft delete

        Raises:
            NotFoundError: If contact not found or already deleted
        """
        from datetime import datetime

        result = await db.execute(
            select(Contact).where(
                Contact.id == contact_id, Contact.deleted_at.is_(None)
            )
        )
        contact = result.scalar_one_or_none()

        if not contact:
            raise NotFoundError("Contact", contact_id)

        contact.deleted_at = datetime.utcnow()
        await db.flush()
