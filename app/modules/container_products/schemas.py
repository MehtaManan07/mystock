"""
ContainerProduct DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime


class ContainerProductItemDto(BaseModel):
    """Individual item in container product payload"""

    productId: int = Field(..., gt=0, description="Product ID")
    quantity: int = Field(..., ge=0, description="Quantity (0 means soft delete)")

    class Config:
        from_attributes = True


class CreateContainerProductDto(BaseModel):
    """DTO for setting products in a container"""

    containerId: int = Field(..., gt=0, description="Container ID")
    items: List[ContainerProductItemDto] = Field(
        ..., min_length=1, description="List of products with quantities"
    )

    class Config:
        from_attributes = True


class ProductInContainerProductResponse(BaseModel):
    """Product data in container-product response"""

    id: int
    name: str
    size: str
    packing: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContainerInContainerProductResponse(BaseModel):
    """Container data in container-product response"""

    id: int
    name: str
    type: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContainerProductResponse(BaseModel):
    """Response model for ContainerProduct entity"""

    id: int
    container_id: int
    product_id: int
    quantity: int
    last_verified_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductInContainerProductResponse] = None
    container: Optional[ContainerInContainerProductResponse] = None

    class Config:
        from_attributes = True


class TotalQuantityResponse(BaseModel):
    """Response for total quantity of a product"""

    productId: int
    totalQuantity: int

    class Config:
        from_attributes = True


class BasicAnalyticsResponse(BaseModel):
    """Response for basic analytics"""

    totalProducts: int
    totalContainers: int
    totalQuantity: int

    class Config:
        from_attributes = True


class MapProductInputDto(BaseModel):
    """Input for mapping products to IDs"""

    name: str
    size: str
    quantity: int

    class Config:
        from_attributes = True


class MapProductOutputDto(BaseModel):
    """Output for mapped product IDs"""

    quantity: int
    productId: Optional[int] = None

    class Config:
        from_attributes = True

