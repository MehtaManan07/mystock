"""
Products Router - FastAPI equivalent of NestJS ProductsController.
Protected with role-based access control.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import (
    TokenData,
    require_admin,
    require_admin_or_staff,
    require_any_role,
)
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
async def create_product(
    dto: CreateProductDto,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_staff)
):
    """Create a new product (Admin/Staff only)"""
    product = await ProductService.create(db, dto)
    await db.commit()
    
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
async def bulk_create_products(
    data: CreateProductBulkDto,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_staff)
):
    """Bulk create products (Admin/Staff only)"""
    products = await ProductService.bulk_create(db, data)
    await db.commit()
    
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
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_any_role)
):
    """
    Get all products with optional search filter. (Requires authentication)
    Returns products with totalQuantity computed from containers.
    """
    products = await ProductService.find_all(db, search)
    return products


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product_by_id(
    product_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_any_role)
):
    """Get product by ID with containers and logs (excludes soft-deleted products) - requires authentication"""
    product = await ProductService.find_one(db, product_id)
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    dto: UpdateProductDto,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_staff)
):
    """Update product information (Admin/Staff only)"""
    product = await ProductService.update(db, product_id, dto)
    await db.commit()
    
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
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin)
):
    """Soft delete product (Admin only)"""
    await ProductService.remove(db, product_id)
    await db.commit()
    return {"message": "Product deleted successfully"}

