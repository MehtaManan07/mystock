"""Company Settings DTOs (Data Transfer Objects)"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CompanySettingsResponse(BaseModel):
    """Response model for company settings"""

    id: int
    company_name: str
    seller_name: str
    seller_phone: str
    seller_email: str
    seller_gstin: str
    company_address_line1: str
    company_address_line2: str
    company_address_line3: str
    terms_and_conditions: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateCompanySettingsDto(BaseModel):
    """DTO for updating company settings"""

    company_name: Optional[str] = Field(None, max_length=255)
    seller_name: Optional[str] = Field(None, max_length=255)
    seller_phone: Optional[str] = Field(None, max_length=50)
    seller_email: Optional[str] = Field(None, max_length=255)
    seller_gstin: Optional[str] = Field(None, max_length=15)
    company_address_line1: Optional[str] = Field(None, max_length=255)
    company_address_line2: Optional[str] = Field(None, max_length=255)
    company_address_line3: Optional[str] = Field(None, max_length=255)
    terms_and_conditions: Optional[str] = Field(None)

    class Config:
        from_attributes = True
