"""
Products Router - FastAPI equivalent of NestJS ProductsController.
Protected with role-based access control.
"""

from typing import List, Optional
from fastapi import APIRouter, File, Query, UploadFile

from app.core.response_interceptor import skip_interceptor
from .service import ProductService
from .schemas import (
    CreateProductDto,
    CreateProductBulkDto,
    UpdateProductDto,
    ProductResponse,
    ProductDetailResponse,
    ProductImageResponse,
    CopyFromProductDto,
    ReorderImagesDto,
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
        company_sku=product.company_sku,
        default_sale_price=product.default_sale_price,
        default_purchase_price=product.default_purchase_price,
        display_name=product.display_name,
        description=product.description,
        mrp=product.mrp,
        tags=product.tags,
        product_type=product.product_type,
        dimensions=product.dimensions,
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
            company_sku=product.company_sku,
            default_sale_price=product.default_sale_price,
            default_purchase_price=product.default_purchase_price,
            display_name=product.display_name,
            description=product.description,
            mrp=product.mrp,
            tags=product.tags,
            product_type=product.product_type,
            dimensions=product.dimensions,
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
        company_sku=product.company_sku,
        default_sale_price=product.default_sale_price,
        default_purchase_price=product.default_purchase_price,
        display_name=product.display_name,
        description=product.description,
        mrp=product.mrp,
        tags=product.tags,
        product_type=product.product_type,
        dimensions=product.dimensions,
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


# --- Product images (must be after /{product_id} routes that don't have subpaths) ---

@router.post("/{product_id}/images", response_model=List[ProductImageResponse])
async def upload_product_images(product_id: int, files: List[UploadFile] = File(...)):
    """Upload images for a product. Max 15 images per product, 10 MB per file. Accepts image/jpeg, image/png, image/webp."""
    print(f"Uploading {len(files)} images for product {product_id}")
    if not files:
        return []
    files_data = []
    for f in files:
        print(f"Processing file: {f.filename}")
        content = await f.read()
        content_type = f.content_type or "application/octet-stream"
        filename = f.filename or "image"
        files_data.append((content, content_type, filename))
    return await ProductService.add_images(product_id, files_data)


@router.post("/{product_id}/images/copy-from", response_model=List[ProductImageResponse])
async def copy_product_images_from(product_id: int, dto: CopyFromProductDto):
    """Copy images from another product. Send image_ids to copy only selected; omit to copy all."""
    return await ProductService.copy_images_from(
        product_id, dto.source_product_id, image_ids=dto.image_ids
    )


@router.delete("/{product_id}/images/{image_id}")
@skip_interceptor
async def delete_product_image(product_id: int, image_id: int):
    """Remove an image from the product. Deletes from GCS only when no other product uses it."""
    await ProductService.delete_image(product_id, image_id)
    return {"message": "Image removed"}


@router.patch("/{product_id}/images/reorder")
async def reorder_product_images(product_id: int, dto: ReorderImagesDto):
    """Reorder images. Body: { \"order\": [image_id1, image_id2, ...] }."""
    await ProductService.reorder_images(product_id, dto.order)
    return {"message": "Order updated"}
