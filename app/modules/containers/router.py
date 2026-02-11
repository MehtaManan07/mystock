"""
Containers Router - FastAPI equivalent of NestJS ContainersController.
Demonstrates how to use ContainerService with run_db pattern.
"""

from typing import List, Optional
from fastapi import APIRouter, Query

from app.core.response_interceptor import skip_interceptor
from .service import ContainerService
from .schemas import (
    CreateContainerDto,
    CreateContainerBulkDto,
    UpdateContainerDto,
    ContainerResponse,
    ContainerDetailResponse,
    ContainerPaginatedResponse,
)

router = APIRouter(prefix="/containers", tags=["containers"])


@router.post("", response_model=ContainerResponse)
async def create_container(dto: CreateContainerDto):
    """Create a new container"""
    container = await ContainerService.create(dto)

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
async def bulk_create_containers(data: CreateContainerBulkDto):
    """Bulk create containers"""
    containers = await ContainerService.bulk_create(data)

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


@router.get("/special/loose-stock", response_model=ContainerResponse)
async def get_loose_stock_container():
    """
    Get the virtual Loose Stock container.
    Creates it if it doesn't exist.
    
    Use this container for products that are not in any physical container
    (e.g., loose items, items in transit, unassigned stock).
    """
    container = await ContainerService.ensure_loose_stock_container()
    
    # Calculate product count
    product_count = sum(1 for cp in container.contents if cp.deleted_at is None) if hasattr(container, 'contents') and container.contents else 0
    
    return ContainerResponse(
        id=container.id,
        name=container.name,
        type=container.type.value,
        deleted_at=container.deleted_at,
        created_at=container.created_at,
        updated_at=container.updated_at,
        productCount=product_count,
    )


@router.get("", response_model=ContainerPaginatedResponse)
async def get_all_containers(
    search: Optional[str] = Query(None, description="Search by container name"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (max 100)"),
):
    """
    Get all containers with pagination and optional search filter.
    Search filtering is applied server-side before pagination.

    Containers are sorted by numeric value extracted from name (DESC) within each page.

    Query Parameters:
        - search: Optional search term
        - page: Page number starting from 1
        - page_size: Number of items per page (default 25, max 100)

    Response includes:
        - items: List of containers for current page
        - total: Total number of containers matching search
        - page: Current page number
        - page_size: Items per page
        - total_pages: Total pages available
        - has_more: Boolean indicating if more pages exist
    """
    result = await ContainerService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
    )
    return result


@router.get("/{container_id}", response_model=ContainerDetailResponse)
async def get_container_by_id(container_id: int):
    """Get container by ID with products and logs (excludes soft-deleted containers)"""
    container = await ContainerService.find_one_formatted(container_id)
    return container


@router.patch("/{container_id}", response_model=ContainerResponse)
async def update_container(container_id: int, dto: UpdateContainerDto):
    """Update container information"""
    container = await ContainerService.update(container_id, dto)

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
async def delete_container(container_id: int):
    """Soft delete container (returns custom response format)"""
    await ContainerService.remove(container_id)
    return {"message": "Container deleted successfully"}
