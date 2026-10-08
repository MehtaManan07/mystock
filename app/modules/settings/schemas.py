"""Company Settings DTOs (Data Transfer Objects)"""

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
from typing import Optional
from datetime import datetime


class CompanyBankDetails(BaseModel):
    """Bank fields are optional as a group; branch name/code is optional."""

    bank_name: Optional[str] = Field(None, max_length=255)
    bank_account_number: Optional[str] = Field(None, max_length=50, pattern=r"^[0-9]+$")
    bank_branch: Optional[str] = Field(None, max_length=255)
    bank_ifsc: Optional[str] = Field(None, pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$", max_length=11)

    @field_validator("bank_name", "bank_account_number", "bank_branch", "bank_ifsc", mode="before")
    @classmethod
    def normalize_bank_fields(cls, value, info: ValidationInfo):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if info.field_name == "bank_ifsc":
                return value.upper()
        return value

    @model_validator(mode="after")
    def require_complete_bank_details(self):
        values = (self.bank_name, self.bank_account_number, self.bank_branch, self.bank_ifsc)
        if any(values) and not all((self.bank_name, self.bank_account_number, self.bank_ifsc)):
            raise ValueError("Provide bank name, account number and IFSC together, or clear all bank fields")
        return self

    class Config:
        from_attributes = True


class CompanySettingsResponse(CompanyBankDetails):
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
    hsn_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateCompanySettingsDto(CompanyBankDetails):
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
    hsn_code: Optional[str] = Field(None, max_length=15)

    @model_validator(mode="after")
    def require_bank_group_on_update(self):
        fields = {"bank_name", "bank_account_number", "bank_branch", "bank_ifsc"}
        if fields & self.model_fields_set and not fields <= self.model_fields_set:
            raise ValueError("Include all four bank fields when updating or clearing bank details")
        return self

    class Config:
        from_attributes = True
