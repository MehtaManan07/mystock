"""
Contacts Router - FastAPI routes for contacts management.
Demonstrates CRUD operations with run_db pattern.
"""

from typing import List
from fastapi import APIRouter, Depends

from app.core.response_interceptor import skip_interceptor
from .service import ContactsService
from .schemas import ContactResponse, CreateContactDto, UpdateContactDto, FilterContactsDto

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactResponse, status_code=201)
async def create_contact(create_dto: CreateContactDto):
    """Create a new contact"""
    contact = await ContactsService.create(create_dto)
    return contact


@router.get("", response_model=List[ContactResponse])
async def get_all_contacts(filters: FilterContactsDto = Depends()):
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
    - GET /contacts?search=John - Search by name or phone
    """
    contacts = await ContactsService.find_all(filters=filters)
    return contacts


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact_by_id(contact_id: int):
    """Get contact by ID (excludes soft-deleted contacts)"""
    contact = await ContactsService.find_one(contact_id)
    return contact


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(contact_id: int, update_dto: UpdateContactDto):
    """Update contact information"""
    contact = await ContactsService.update(contact_id, update_dto)
    return contact


@router.delete("/{contact_id}")
@skip_interceptor
async def delete_contact(contact_id: int):
    """Soft delete contact (returns custom response format)"""
    await ContactsService.remove(contact_id)
    return {"message": "Contact deleted successfully"}
