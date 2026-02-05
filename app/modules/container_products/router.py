"""
ContainerProducts Router - FastAPI equivalent of NestJS ContainerProductController.
Handles inventory management between containers and products.
"""

from typing import List
from fastapi import APIRouter, Query

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
async def set_products_in_container(dto: CreateContainerProductDto):
    """
    Set products in a container with quantities.
    This method handles:
    - Creating new container-product relationships
    - Updating existing quantities
    - Soft-deleting when quantity is 0
    - Creating audit logs for all changes
    
    Uses pessimistic locking to prevent race conditions.
    """
    await ContainerProductService.set_products_in_container(dto)
    return {"message": "Products updated successfully"}


@router.post("/{container_id}/products/{product_id}/verify")
@skip_interceptor
async def verify_product_location(container_id: int, product_id: int):
    """
    Mark a product-container location as verified now.
    Updates the last_verified_at timestamp without changing quantity.
    Use this when staff confirms "yes, this product is still in this container".
    """
    await ContainerProductService.verify_product_location(container_id, product_id)
    return {"message": "Location verified successfully"}


@router.get("/{container_id}/products", response_model=List[ContainerProductResponse])
async def get_products_in_container(container_id: int):
    """
    Get all products in a specific container.
    Returns container-product relationships with product details.
    """
    items = await ContainerProductService.get_products_in_container(container_id)
    return items


@router.get(
    "/product/{product_id}/containers", response_model=List[ContainerProductResponse]
)
async def get_containers_for_product(product_id: int):
    """
    Get all containers that have a specific product.
    Returns container-product relationships with container details.
    """
    items = await ContainerProductService.get_containers_for_product(product_id)
    return items


@router.get("/search", response_model=List[ContainerProductResponse])
async def search_containers_by_sku(
    sku: str = Query(..., description="Product name/SKU to search for"),
):
    """
    Search for containers by product SKU (name).
    Case-insensitive partial match on product name.
    """
    items = await ContainerProductService.search_containers_by_sku(sku)
    return items


@router.get(
    "/product/{product_id}/total-quantity", response_model=TotalQuantityResponse
)
async def get_total_quantity_of_sku(product_id: int):
    """
    Get total quantity of a product across all containers.
    Excludes soft-deleted container-product relationships.
    """
    result = await ContainerProductService.get_total_quantity_of_sku(product_id)
    return result


@router.get("/analytics", response_model=BasicAnalyticsResponse)
async def get_basic_analytics():
    """
    Get basic analytics:
    - Total number of products
    - Total number of containers
    - Total quantity across all container-product relationships
    """
    result = await ContainerProductService.get_basic_analytics()
    return result


@router.post("/map-products-to-ids", response_model=List[MapProductOutputDto])
async def map_products_to_ids(input_data: List[MapProductInputDto]):
    """
    Map product names and sizes to their database IDs.
    Useful for bulk operations where you have product details but need IDs.
    
    Uses efficient bulk SQL query for performance.
    """
    result = await ContainerProductService.map_products_to_ids(input_data)
    return result
