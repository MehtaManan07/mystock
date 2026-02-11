"""
Product DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class CreateProductDto(BaseModel):
    """DTO for creating a single product"""

    name: str = Field(..., min_length=1, max_length=255)
    size: str = Field(..., min_length=1, max_length=255)
    packing: str = Field(..., min_length=1, max_length=255)
    company_sku: Optional[str] = Field(None, max_length=100, description="Company SKU (optional)")
    default_sale_price: Optional[Decimal] = Field(None, ge=0, description="Default sale price")
    default_purchase_price: Optional[Decimal] = Field(None, ge=0, description="Default purchase price")
    display_name: Optional[str] = Field(None, max_length=255, description="Display name")
    description: Optional[str] = Field(None, description="Product description")
    mrp: Optional[Decimal] = Field(None, ge=0, description="Maximum retail price")
    tags: Optional[List[str]] = Field(None, description="Product tags")
    product_type: Optional[str] = Field(None, max_length=255, description="Product category/type")
    dimensions: Optional[Dict[str, Any]] = Field(None, description="Product dimensions (width, height, length in cm)")

    @field_validator('dimensions')
    @classmethod
    def validate_dimensions(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v
        required_keys = {'width', 'height', 'length'}
        if not all(key in v for key in required_keys):
            raise ValueError('dimensions must contain width, height, and length')
        for key in required_keys:
            if not isinstance(v[key], (int, float)) or v[key] <= 0:
                raise ValueError(f'{key} must be a positive number')
        return v

    class Config:
        from_attributes = True


class CreateProductBulkDto(BaseModel):
    """DTO for bulk creating products"""

    data: List[CreateProductDto]

    class Config:
        from_attributes = True


class UpdateProductDto(BaseModel):
    """DTO for updating product information"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    size: Optional[str] = Field(None, min_length=1, max_length=255)
    packing: Optional[str] = Field(None, min_length=1, max_length=255)
    company_sku: Optional[str] = Field(None, max_length=100, description="Company SKU")
    default_sale_price: Optional[Decimal] = Field(None, ge=0, description="Default sale price")
    default_purchase_price: Optional[Decimal] = Field(None, ge=0, description="Default purchase price")
    display_name: Optional[str] = Field(None, max_length=255, description="Display name")
    description: Optional[str] = Field(None, description="Product description")
    mrp: Optional[Decimal] = Field(None, ge=0, description="Maximum retail price")
    tags: Optional[List[str]] = Field(None, description="Product tags")
    product_type: Optional[str] = Field(None, max_length=255, description="Product category/type")
    dimensions: Optional[Dict[str, Any]] = Field(None, description="Product dimensions (width, height, length in cm)")

    @field_validator('dimensions')
    @classmethod
    def validate_dimensions(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v
        required_keys = {'width', 'height', 'length'}
        if not all(key in v for key in required_keys):
            raise ValueError('dimensions must contain width, height, and length')
        for key in required_keys:
            if not isinstance(v[key], (int, float)) or v[key] <= 0:
                raise ValueError(f'{key} must be a positive number')
        return v

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    """Response model for Product entity (list view with total quantity)"""

    id: int
    name: str
    size: str
    packing: str
    company_sku: Optional[str] = None
    default_sale_price: Optional[Decimal] = None
    default_purchase_price: Optional[Decimal] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    mrp: Optional[Decimal] = None
    tags: Optional[List[str]] = None
    product_type: Optional[str] = None
    dimensions: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    totalQuantity: int

    class Config:
        from_attributes = True


class ContainerInProductResponse(BaseModel):
    """Container data in product detail response"""

    id: int
    name: str
    type: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContainerProductResponse(BaseModel):
    """Container with quantity in product detail"""

    container: ContainerInProductResponse
    quantity: int

    class Config:
        from_attributes = True


class LogContainerResponse(BaseModel):
    """Minimal container info in log"""

    id: int
    name: str

    class Config:
        from_attributes = True


class LogResponse(BaseModel):
    """Log entry in product detail"""

    id: int
    quantity: int
    action: str
    container: Optional[LogContainerResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class VendorSkuInfo(BaseModel):
    """Vendor SKU information"""
    
    vendor_id: int
    vendor_name: str
    vendor_sku: str
    
    class Config:
        from_attributes = True


class ProductImageResponse(BaseModel):
    """Product image in detail response"""

    id: int
    url: str
    thumb_url: str
    sort_order: int

    class Config:
        from_attributes = True


class CopyFromProductDto(BaseModel):
    """DTO for copying images from another product. If image_ids omitted, copy all."""

    source_product_id: int
    image_ids: Optional[List[int]] = None  # If set, copy only these image IDs (from source product)


class ReorderImagesDto(BaseModel):
    """DTO for reordering product images"""

    order: List[int]


class ProductDetailResponse(BaseModel):
    """Detailed response model for Product entity with relationships"""

    id: int
    name: str
    size: str
    packing: str
    company_sku: Optional[str] = None
    default_sale_price: Optional[Decimal] = None
    default_purchase_price: Optional[Decimal] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    mrp: Optional[Decimal] = None
    tags: Optional[List[str]] = None
    product_type: Optional[str] = None
    dimensions: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    containers: List[ContainerProductResponse]
    logs: List[LogResponse]
    vendor_skus: List[VendorSkuInfo] = []
    images: List[ProductImageResponse] = []

    class Config:
        from_attributes = True


class ProductPaginatedResponse(BaseModel):
    """Paginated response for products list"""

    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True

