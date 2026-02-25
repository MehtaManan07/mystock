"""
Drafts DTOs (Data Transfer Objects)
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from .models import DraftType
from app.modules.products.schemas import ProductResponse
from app.modules.containers.schemas import ContainerResponse


class DraftItemData(BaseModel):
    """Individual item in draft transaction"""
    productId: int
    containerId: int
    quantity: int
    unitPrice: float | str


class DraftDataModel(BaseModel):
    """Structure of draft data"""
    transactionDate: str
    contactId: int | None = None
    items: List[DraftItemData]
    taxPercent: float = 0
    discountAmount: float = 0
    paidAmount: float = 0
    paymentMethod: Optional[str] = None
    paymentReference: Optional[str] = None
    notes: Optional[str] = None
    productDetailsDisplayMode: Optional[str] = None


class CreateDraftDto(BaseModel):
    """DTO for creating a draft"""
    type: DraftType = Field(..., description="Type of draft (sale or purchase)")
    name: str = Field(..., min_length=1, max_length=255, description="Draft name")
    data: DraftDataModel = Field(..., description="Draft form data as JSON object")

    class Config:
        from_attributes = True


class UpdateDraftDto(BaseModel):
    """DTO for updating a draft"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Draft name")
    data: Optional[DraftDataModel] = Field(None, description="Draft form data as JSON object")

    class Config:
        from_attributes = True


class DraftResponse(BaseModel):
    """Response model for draft"""
    id: int
    user_id: int
    type: str
    name: str
    data: Dict[str, Any]  # JSON object
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HydratedDraftItem(BaseModel):
    """Draft item with hydrated product and container data"""
    productId: int
    containerId: int
    quantity: int
    unitPrice: float | str
    product: ProductResponse
    container: ContainerResponse

    class Config:
        from_attributes = True


class CompleteDraftResponse(BaseModel):
    """Complete draft response with hydrated products and containers"""
    id: int
    user_id: int
    type: str
    name: str
    created_at: datetime
    updated_at: datetime
    items: List[HydratedDraftItem]
    transactionDate: str
    contactId: int | None
    taxPercent: float
    discountAmount: float
    paidAmount: float
    paymentMethod: str | None
    paymentReference: str | None
    notes: str | None
    productDetailsDisplayMode: str | None

    class Config:
        from_attributes = True
