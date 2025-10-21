"""
ContainerProducts Router - FastAPI equivalent of NestJS ContainerProductController.
Handles inventory management between containers and products.
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from .service import ContainerProductService
from .schemas import (
    CreateContainerProductDto,
    ContainerProductResponse,
    TotalQuantityResponse,
    BasicAnalyticsResponse,
    MapProductInputDto,
    MapProductOutputDto,
)

router = APIRouter(prefix="/container-products", tags=["container-products"])


@router.post("/set-products")
@skip_interceptor
async def set_products_in_container(
    dto: CreateContainerProductDto, db: AsyncSession = Depends(get_db_util)
):
    """
    Set products in a container with quantities.
    This method handles:
    - Creating new container-product relationships
    - Updating existing quantities
    - Soft-deleting when quantity is 0
    - Creating audit logs for all changes
    
    Uses pessimistic locking to prevent race conditions.
    """
    await ContainerProductService.set_products_in_container(db, dto)
    await db.commit()
    return {"message": "Products updated successfully"}


@router.get("/{container_id}/products", response_model=List[ContainerProductResponse])
async def get_products_in_container(
    container_id: int, db: AsyncSession = Depends(get_db_util)
):
    """
    Get all products in a specific container.
    Returns container-product relationships with product details.
    """
    items = await ContainerProductService.get_products_in_container(
        db, container_id
    )
    
    # Map to response format
    return [
        ContainerProductResponse(
            id=item.id,
            container_id=item.container_id,
            product_id=item.product_id,
            quantity=item.quantity,
            deleted_at=item.deleted_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            product=item.product,
        )
        for item in items
    ]


@router.get(
    "/product/{product_id}/containers", response_model=List[ContainerProductResponse]
)
async def get_containers_for_product(
    product_id: int, db: AsyncSession = Depends(get_db_util)
):
    """
    Get all containers that have a specific product.
    Returns container-product relationships with container details.
    """
    items = await ContainerProductService.get_containers_for_product(db, product_id)
    
    # Map to response format
    return [
        ContainerProductResponse(
            id=item.id,
            container_id=item.container_id,
            product_id=item.product_id,
            quantity=item.quantity,
            deleted_at=item.deleted_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            container=item.container,
        )
        for item in items
    ]


@router.get("/search", response_model=List[ContainerProductResponse])
async def search_containers_by_sku(
    sku: str = Query(..., description="Product name/SKU to search for"),
    db: AsyncSession = Depends(get_db_util),
):
    """
    Search for containers by product SKU (name).
    Case-insensitive partial match on product name.
    """
    items = await ContainerProductService.search_containers_by_sku(db, sku)
    
    # Map to response format
    return [
        ContainerProductResponse(
            id=item.id,
            container_id=item.container_id,
            product_id=item.product_id,
            quantity=item.quantity,
            deleted_at=item.deleted_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            product=item.product,
            container=item.container,
        )
        for item in items
    ]


@router.get(
    "/product/{product_id}/total-quantity", response_model=TotalQuantityResponse
)
async def get_total_quantity_of_sku(
    product_id: int, db: AsyncSession = Depends(get_db_util)
):
    """
    Get total quantity of a product across all containers.
    Excludes soft-deleted container-product relationships.
    """
    result = await ContainerProductService.get_total_quantity_of_sku(db, product_id)
    return result


@router.get("/analytics", response_model=BasicAnalyticsResponse)
async def get_basic_analytics(db: AsyncSession = Depends(get_db_util)):
    """
    Get basic analytics:
    - Total number of products
    - Total number of containers
    - Total quantity across all container-product relationships
    """
    result = await ContainerProductService.get_basic_analytics(db)
    return result


@router.post("/map-products-to-ids", response_model=List[MapProductOutputDto])
async def map_products_to_ids(
    input_data: List[MapProductInputDto], db: AsyncSession = Depends(get_db_util)
):
    """
    Map product names and sizes to their database IDs.
    Useful for bulk operations where you have product details but need IDs.
    
    Uses efficient bulk SQL query for performance.
    """
    result = await ContainerProductService.map_products_to_ids(db, input_data)
    return result

