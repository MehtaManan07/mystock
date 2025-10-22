"""
Contacts Router - FastAPI routes for contacts management.
Demonstrates CRUD operations with dependency injection.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from .service import ContactsService
from .schemas import ContactResponse, CreateContactDto, UpdateContactDto, FilterContactsDto

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactResponse, status_code=201)
async def create_contact(
    create_dto: CreateContactDto,
    db: AsyncSession = Depends(get_db_util)
):
    """Create a new contact"""
    contact = await ContactsService.create(db, create_dto)
    return contact


@router.get("", response_model=List[ContactResponse])
async def get_all_contacts(
    filters: FilterContactsDto = Depends(),
    db: AsyncSession = Depends(get_db_util)
):
    """
    Get all contacts with optional filters.
    
    Query parameters:
    - types: Filter by contact type(s). Can pass multiple: ?types=customer&types=supplier
    - balance: Filter by balance type - 'positive' for receivables, 'negative' for payables
    - search: Search by name or phone
    
    Examples:
    - GET /contacts - Get all active contacts
    - GET /contacts?types=customer - Get all customers
    - GET /contacts?balance=positive - Get all receivables
    - GET /contacts?types=supplier&balance=negative - Get suppliers you owe
    """
    contacts = await ContactsService.find_all(db=db, filters=filters)
    return contacts


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact_by_id(
    contact_id: int,
    db: AsyncSession = Depends(get_db_util)
):
    """Get contact by ID (excludes soft-deleted contacts)"""
    contact = await ContactsService.find_one(db, contact_id)
    return contact


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    update_dto: UpdateContactDto,
    db: AsyncSession = Depends(get_db_util)
):
    """Update contact information"""
    contact = await ContactsService.update(db, contact_id, update_dto)
    return contact


@router.delete("/{contact_id}")
@skip_interceptor
async def delete_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db_util)
):
    """Soft delete contact (returns custom response format)"""
    await ContactsService.remove(db, contact_id)
    return {"message": "Contact deleted successfully"}

