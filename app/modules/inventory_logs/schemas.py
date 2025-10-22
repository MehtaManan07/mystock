"""
InventoryLog DTOs - Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class CreateInventoryLogDto(BaseModel):
    """DTO for creating a single inventory log."""

    product_id: int = Field(..., description="Product ID")
    container_id: int = Field(..., description="Container ID")
    quantity: int = Field(..., description="Quantity of the action")
    action: str = Field(..., description="Action type (e.g., 'add', 'remove', 'transfer')")
    note: str | None = Field(None, description="Optional note about the action")


class CreateInventoryLogBulkDto(BaseModel):
    """DTO for creating multiple inventory logs in bulk."""

    data: List[CreateInventoryLogDto] = Field(..., description="List of inventory logs to create")


class InventoryLogResponse(BaseModel):
    """Response schema for inventory log."""

    id: int
    product_id: int
    container_id: int
    quantity: int
    action: str
    note: str | None
    timestamp: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = {"from_attributes": True}

