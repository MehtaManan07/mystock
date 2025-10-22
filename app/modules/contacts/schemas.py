"""
Contact DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from .models import ContactType


class FilterContactsDto(BaseModel):
    """DTO for filtering contacts"""

    types: Optional[List[ContactType]] = None
    balance: Optional[str] = Field(None, pattern="^(positive|negative)$")
    search: Optional[str] = Field(None, description="Search by name or phone")


class CreateContactDto(BaseModel):
    """DTO for creating a new contact"""

    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=1, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    gstin: Optional[str] = Field(None, max_length=15)
    type: ContactType = ContactType.customer
    balance: Decimal = Field(default=Decimal("0.0"))

    class Config:
        from_attributes = True


class UpdateContactDto(BaseModel):
    """DTO for updating contact information"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, min_length=1, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    gstin: Optional[str] = Field(None, max_length=15)
    type: Optional[ContactType] = None
    balance: Optional[Decimal] = None

    class Config:
        from_attributes = True


class ContactResponse(BaseModel):
    """Response model for Contact entity"""

    id: int
    name: str
    phone: str
    address: Optional[str] = None
    gstin: Optional[str] = None
    type: ContactType
    balance: Decimal
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
