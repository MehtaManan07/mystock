"""
InventoryLog Router - API endpoints for inventory log management.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from .service import InventoryLogService
from .schemas import (
    CreateInventoryLogDto,
    CreateInventoryLogBulkDto,
    InventoryLogResponse,
)

router = APIRouter(prefix="/inventory-logs", tags=["Inventory Logs"])


@router.post("/", response_model=InventoryLogResponse, status_code=201)
async def create_log(
    dto: CreateInventoryLogDto,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Create a single inventory log.
    
    Args:
        dto: Inventory log creation data
        db: Database session
        
    Returns:
        Created inventory log
    """
    log = await InventoryLogService.create_log(db, dto)
    return log


@router.post("/bulk", response_model=List[InventoryLogResponse], status_code=201)
async def create_logs_bulk(
    dtos: CreateInventoryLogBulkDto,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Create multiple inventory logs in bulk.
    
    Args:
        dtos: Bulk inventory log creation data
        db: Database session
        
    Returns:
        List of created inventory logs
    """
    logs = await InventoryLogService.create_logs_bulk(db, dtos)
    return logs


@router.get("/product/{product_id}", response_model=List[InventoryLogResponse])
async def get_logs_for_product(
    product_id: int,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get all inventory logs for a specific product.
    
    Args:
        product_id: Product ID to filter by
        db: Database session
        
    Returns:
        List of inventory logs for the product
    """
    logs = await InventoryLogService.get_logs_for_product(db, product_id)
    return logs


@router.get("/container/{container_id}", response_model=List[InventoryLogResponse])
async def get_logs_for_container(
    container_id: int,
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get all inventory logs for a specific container.
    
    Args:
        container_id: Container ID to filter by
        db: Database session
        
    Returns:
        List of inventory logs for the container
    """
    logs = await InventoryLogService.get_logs_for_container(db, container_id)
    return logs


@router.get("/", response_model=List[InventoryLogResponse])
async def get_all_logs(
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get all inventory logs.
    
    Args:
        db: Database session
        
    Returns:
        List of all inventory logs
    """
    logs = await InventoryLogService.get_all_logs(db)
    return logs

