"""Vendor Product SKU DTOs (Data Transfer Objects)"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreateVendorSkuDto(BaseModel):
    """DTO for creating a vendor SKU mapping"""

    product_id: int = Field(..., gt=0, description="Product ID")
    vendor_id: int = Field(..., gt=0, description="Vendor/Contact ID")
    vendor_sku: str = Field(..., min_length=1, max_length=100, description="Vendor's SKU for this product")

    class Config:
        from_attributes = True


class UpdateVendorSkuDto(BaseModel):
    """DTO for updating a vendor SKU mapping"""

    vendor_sku: str = Field(..., min_length=1, max_length=100, description="Vendor's SKU for this product")

    class Config:
        from_attributes = True


class VendorSkuResponse(BaseModel):
    """Response model for vendor SKU mapping"""

    id: int
    product_id: int
    vendor_id: int
    vendor_sku: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VendorSkuDetailResponse(BaseModel):
    """Detailed response for vendor SKU with vendor name"""

    id: int
    product_id: int
    vendor_id: int
    vendor_name: str
    vendor_sku: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
