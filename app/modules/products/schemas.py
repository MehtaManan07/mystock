"""
Product DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateProductDto(BaseModel):
    """DTO for creating a single product"""

    name: str = Field(..., min_length=1, max_length=255)
    size: str = Field(..., min_length=1, max_length=255)
    packing: str = Field(..., min_length=1, max_length=255)

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

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    """Response model for Product entity (list view with total quantity)"""

    id: int
    name: str
    size: str
    packing: str
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


class ProductDetailResponse(BaseModel):
    """Detailed response model for Product entity with relationships"""

    id: int
    name: str
    size: str
    packing: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    containers: List[ContainerProductResponse]
    logs: List[LogResponse]

    class Config:
        from_attributes = True

