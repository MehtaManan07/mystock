"""
Containers Router - FastAPI equivalent of NestJS ContainersController.
Demonstrates how to use ContainerService with dependency injection.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from .service import ContainerService
from .schemas import (
    CreateContainerDto,
    CreateContainerBulkDto,
    UpdateContainerDto,
    ContainerResponse,
    ContainerDetailResponse,
)

router = APIRouter(prefix="/containers", tags=["containers"])


@router.post("", response_model=ContainerResponse)
async def create_container(
    dto: CreateContainerDto, db: AsyncSession = Depends(get_db_util)
):
    """Create a new container"""
    container = await ContainerService.create(db, dto)
    await db.commit()

    # Return with productCount = 0 for new containers
    return ContainerResponse(
        id=container.id,
        name=container.name,
        type=container.type.value,
        deleted_at=container.deleted_at,
        created_at=container.created_at,
        updated_at=container.updated_at,
        productCount=0,
    )


@router.post("/bulk", response_model=List[ContainerResponse])
async def bulk_create_containers(
    data: CreateContainerBulkDto, db: AsyncSession = Depends(get_db_util)
):
    """Bulk create containers"""
    containers = await ContainerService.bulk_create(db, data)
    await db.commit()

    # Return containers with productCount = 0 for new containers
    return [
        ContainerResponse(
            id=container.id,
            name=container.name,
            type=container.type.value,
            deleted_at=container.deleted_at,
            created_at=container.created_at,
            updated_at=container.updated_at,
            productCount=0,
        )
        for container in containers
    ]


@router.get("", response_model=List[ContainerResponse])
async def get_all_containers(
    search: Optional[str] = Query(None, description="Search by name"),
    db: AsyncSession = Depends(get_db_util),
):
    """
    Get all containers with optional search filter.
    Returns containers with productCount computed from container_products.
    Sorted by numeric value extracted from name (DESC).
    """
    containers = await ContainerService.find_all(db, search)
    return containers


@router.get("/{container_id}", response_model=ContainerDetailResponse)
async def get_container_by_id(
    container_id: int, db: AsyncSession = Depends(get_db_util)
):
    """Get container by ID with products and logs (excludes soft-deleted containers)"""
    container = await ContainerService.find_one_formatted(db, container_id)
    return container


@router.patch("/{container_id}", response_model=ContainerResponse)
async def update_container(
    container_id: int,
    dto: UpdateContainerDto,
    db: AsyncSession = Depends(get_db_util),
):
    """Update container information"""
    container = await ContainerService.update(db, container_id, dto)
    await db.commit()

    # Return with productCount = 0 (or you could recalculate if needed)
    return ContainerResponse(
        id=container.id,
        name=container.name,
        type=container.type.value,
        deleted_at=container.deleted_at,
        created_at=container.created_at,
        updated_at=container.updated_at,
        productCount=0,
    )


@router.delete("/{container_id}")
@skip_interceptor
async def delete_container(
    container_id: int, db: AsyncSession = Depends(get_db_util)
):
    """Soft delete container (returns custom response format)"""
    await ContainerService.remove(db, container_id)
    await db.commit()
    return {"message": "Container deleted successfully"}

