"""
InventoryLog Router - API endpoints for inventory log management.
"""

from typing import List
from fastapi import APIRouter

from .service import InventoryLogService
from .schemas import (
    CreateInventoryLogDto,
    CreateInventoryLogBulkDto,
    InventoryLogResponse,
)

router = APIRouter(prefix="/inventory-logs", tags=["Inventory Logs"])


@router.post("", response_model=InventoryLogResponse, status_code=201)
async def create_log(dto: CreateInventoryLogDto):
    """
    Create a single inventory log.
    
    Args:
        dto: Inventory log creation data
        
    Returns:
        Created inventory log
    """
    log = await InventoryLogService.create_log(dto)
    return log


@router.post("/bulk", response_model=List[InventoryLogResponse], status_code=201)
async def create_logs_bulk(dtos: CreateInventoryLogBulkDto):
    """
    Create multiple inventory logs in bulk.
    
    Args:
        dtos: Bulk inventory log creation data
        
    Returns:
        List of created inventory logs
    """
    logs = await InventoryLogService.create_logs_bulk(dtos)
    return logs


@router.get("/product/{product_id}", response_model=List[InventoryLogResponse])
async def get_logs_for_product(product_id: int):
    """
    Get all inventory logs for a specific product.
    
    Args:
        product_id: Product ID to filter by
        
    Returns:
        List of inventory logs for the product
    """
    logs = await InventoryLogService.get_logs_for_product(product_id)
    return logs


@router.get("/container/{container_id}", response_model=List[InventoryLogResponse])
async def get_logs_for_container(container_id: int):
    """
    Get all inventory logs for a specific container.
    
    Args:
        container_id: Container ID to filter by
        
    Returns:
        List of inventory logs for the container
    """
    logs = await InventoryLogService.get_logs_for_container(container_id)
    return logs


@router.get("", response_model=List[InventoryLogResponse])
async def get_all_logs():
    """
    Get all inventory logs.
        
    Returns:
        List of all inventory logs
    """
    logs = await InventoryLogService.get_all_logs()
    return logs
