"""
Container DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateContainerDto(BaseModel):
    """DTO for creating a single container"""

    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., description="Container type: 'single' or 'mixed'")

    class Config:
        from_attributes = True


class CreateContainerBulkDto(BaseModel):
    """DTO for bulk creating containers"""

    data: List[CreateContainerDto]

    class Config:
        from_attributes = True


class UpdateContainerDto(BaseModel):
    """DTO for updating container information"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, description="Container type: 'single' or 'mixed'")

    class Config:
        from_attributes = True


class ContainerResponse(BaseModel):
    """Response model for Container entity (list view with product count)"""

    id: int
    name: str
    type: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    productCount: int

    class Config:
        from_attributes = True


class ProductInContainerResponse(BaseModel):
    """Product data in container detail response"""

    id: int
    name: str
    size: str
    packing: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductContainerResponse(BaseModel):
    """Product with quantity in container detail"""

    product: ProductInContainerResponse
    quantity: int

    class Config:
        from_attributes = True


class LogProductResponse(BaseModel):
    """Minimal product info in log"""

    id: int
    name: str

    class Config:
        from_attributes = True


class ContainerLogResponse(BaseModel):
    """Log entry in container detail"""

    id: int
    quantity: int
    action: str
    product: Optional[LogProductResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class ContainerDetailResponse(BaseModel):
    """Detailed response model for Container entity with relationships"""

    id: int
    name: str
    type: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    products: List[ProductContainerResponse]
    logs: List[ContainerLogResponse]

    class Config:
        from_attributes = True


class ContainerPaginatedResponse(BaseModel):
    """Paginated response for containers list"""

    items: List[ContainerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True

