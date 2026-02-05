"""
Products Router - FastAPI equivalent of NestJS ProductsController.
Protected with role-based access control.
"""

from typing import List, Optional
from fastapi import APIRouter, Query

from app.core.response_interceptor import skip_interceptor
from .service import ProductService
from .schemas import (
    CreateProductDto,
    CreateProductBulkDto,
    UpdateProductDto,
    ProductResponse,
    ProductDetailResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse)
async def create_product(dto: CreateProductDto):
    """Create a new product"""
    product = await ProductService.create(dto)
    
    # Return with totalQuantity = 0 for new products
    return ProductResponse(
        id=product.id,
        name=product.name,
        size=product.size,
        packing=product.packing,
        deleted_at=product.deleted_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
        totalQuantity=0,
    )


@router.post("/bulk", response_model=List[ProductResponse])
async def bulk_create_products(data: CreateProductBulkDto):
    """Bulk create products"""
    products = await ProductService.bulk_create(data)
    
    # Return products with totalQuantity = 0 for new products
    return [
        ProductResponse(
            id=product.id,
            name=product.name,
            size=product.size,
            packing=product.packing,
            deleted_at=product.deleted_at,
            created_at=product.created_at,
            updated_at=product.updated_at,
            totalQuantity=0,
        )
        for product in products
    ]


@router.get("", response_model=List[ProductResponse])
async def get_all_products(
    search: Optional[str] = Query(None, description="Search by name, size, or packing"),
):
    """
    Get all products with optional search filter.
    Returns products with totalQuantity computed from containers.
    """
    products = await ProductService.find_all(search)
    return products


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product_by_id(product_id: int):
    """Get product by ID with containers and logs (excludes soft-deleted products)"""
    product = await ProductService.find_one(product_id)
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, dto: UpdateProductDto):
    """Update product information"""
    product = await ProductService.update(product_id, dto)
    
    # Return with totalQuantity = 0 (or you could recalculate if needed)
    return ProductResponse(
        id=product.id,
        name=product.name,
        size=product.size,
        packing=product.packing,
        deleted_at=product.deleted_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
        totalQuantity=0,
    )


@router.delete("/{product_id}")
@skip_interceptor
async def delete_product(product_id: int):
    """Soft delete product"""
    await ProductService.remove(product_id)
    return {"message": "Product deleted successfully"}
