"""Vendor Product SKU Router - API endpoints for vendor SKU management."""

from typing import List
from fastapi import APIRouter, status

from app.core.response_interceptor import skip_interceptor
from app.modules.vendor_product_skus.service import VendorSkuService
from app.modules.vendor_product_skus.schemas import (
    CreateVendorSkuDto,
    UpdateVendorSkuDto,
    VendorSkuResponse,
    VendorSkuDetailResponse,
)

router = APIRouter(prefix="/vendor-skus", tags=["vendor-skus"])


@router.post("", response_model=VendorSkuResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_sku(dto: CreateVendorSkuDto):
    """
    Create a new vendor SKU mapping.
    
    Creates a mapping between a product and vendor with a vendor-specific SKU.
    """
    vendor_sku = await VendorSkuService.create_vendor_sku(dto)
    return vendor_sku


@router.get("/products/{product_id}", response_model=List[VendorSkuDetailResponse])
async def get_vendor_skus_for_product(product_id: int):
    """
    Get all vendor SKU mappings for a specific product.
    
    Returns a list of all vendors and their SKUs for the specified product.
    """
    return await VendorSkuService.get_vendor_skus_for_product(product_id)


@router.get("/products/{product_id}/vendors/{vendor_id}", response_model=dict)
async def get_vendor_sku(product_id: int, vendor_id: int):
    """
    Get vendor SKU for a specific product-vendor combination.
    
    Returns the vendor SKU if mapping exists, otherwise returns company SKU as fallback.
    """
    vendor_sku = await VendorSkuService.get_vendor_sku(product_id, vendor_id)
    return {"vendor_sku": vendor_sku}


@router.patch("/products/{product_id}/vendors/{vendor_id}", response_model=VendorSkuResponse)
async def update_vendor_sku(
    product_id: int,
    vendor_id: int,
    dto: UpdateVendorSkuDto,
):
    """
    Update an existing vendor SKU mapping.
    
    Updates the vendor SKU for a specific product-vendor combination.
    """
    vendor_sku = await VendorSkuService.update_vendor_sku(product_id, vendor_id, dto)
    return vendor_sku


@router.delete("/products/{product_id}/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
@skip_interceptor
async def delete_vendor_sku(product_id: int, vendor_id: int):
    """
    Delete a vendor SKU mapping (soft delete).
    
    Removes the vendor-specific SKU mapping. After deletion, the system will
    fall back to using the company SKU for this vendor.
    """
    await VendorSkuService.delete_vendor_sku(product_id, vendor_id)
    return None
