"""
ProductService - FastAPI equivalent of NestJS ProductService.
Optimized queries with eager loading for relationships.
"""

from typing import List, Optional, Dict
from sqlalchemy import select, or_, cast, String
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError

from app.modules.products.schemas import CreateProductDto, CreateProductBulkDto, UpdateProductDto
from app.modules.products.models import Product, ProductImage
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog
from app.modules.vendor_product_skus.models import VendorProductSku


class ProductService:
    """
    Product service with optimized database queries.
    All methods use run_db() for thread-safe Turso operations.
    """

    @staticmethod
    async def create(dto: CreateProductDto) -> Product:
        """
        Create a new product.

        Args:
            dto: Product creation data

        Returns:
            Created product instance
        """
        def _create(db: Session) -> Product:
            product = Product(
                name=dto.name,
                size=dto.size,
                packing=dto.packing,
                company_sku=dto.company_sku,
                default_sale_price=dto.default_sale_price,
                default_purchase_price=dto.default_purchase_price,
                display_name=dto.display_name,
                description=dto.description,
                mrp=dto.mrp,
                tags=dto.tags,
                product_type=dto.product_type,
                dimensions=dto.dimensions,
            )
            db.add(product)
            db.flush()
            db.refresh(product)
            return product
        return await run_db(_create)

    @staticmethod
    async def bulk_create(data: CreateProductBulkDto) -> List[Product]:
        """
        Bulk create products.
        Optimized: Single bulk INSERT + single bulk SELECT instead of N refreshes.

        Args:
            data: Bulk product creation data with list of products

        Returns:
            List of created product instances
        """
        def _bulk_create(db: Session) -> List[Product]:
            products = [
                Product(
                    name=item.name,
                    size=item.size,
                    packing=item.packing,
                    company_sku=item.company_sku,
                    default_sale_price=item.default_sale_price,
                    default_purchase_price=item.default_purchase_price,
                    display_name=item.display_name,
                    description=item.description,
                    mrp=item.mrp,
                    tags=item.tags,
                    product_type=item.product_type,
                    dimensions=item.dimensions,
                )
                for item in data.data
            ]
            db.add_all(products)
            db.flush()

            # Optimization: Instead of N refresh calls, collect IDs and fetch in single query
            product_ids = [product.id for product in products]
            
            # Single SELECT to refresh all products at once
            result = db.execute(
                select(Product).where(Product.id.in_(product_ids))
            )
            refreshed_products = result.scalars().all()
            
            # Return in original order
            id_to_product = {p.id: p for p in refreshed_products}
            return [id_to_product[pid] for pid in product_ids]
        return await run_db(_bulk_create)

    @staticmethod
    async def find_all(search: Optional[str] = None) -> List[dict]:
        """
        Find all products with optional search filter.
        Includes total quantity from containers.
        Optimized: Uses selectinload to prevent N+1 queries.

        Args:
            search: Optional search string to filter by name, size, or packing

        Returns:
            List of products with totalQuantity computed from containers
        """
        def _find_all(db: Session) -> List[dict]:
            # Build query with eager loading
            query = (
                select(Product)
                .where(Product.deleted_at.is_(None))
                .options(
                    selectinload(Product.containers).selectinload(ContainerProduct.container)
                )
            )

            # Add search filter if provided.
            # Split into words; each word must match in at least one searchable field
            # (name, display_name, size, packing, company_sku, description, product_type, tags).
            # e.g. "3.0 inch pagla" or "pagle 3.0 in" matches products with "pagla" in name and "3.0" in size, etc.
            if search:
                words = [w.strip() for w in search.strip().split() if w.strip()]
                for word in words:
                    word_pattern = f"%{word}%"
                    word_matches_any_field = or_(
                        Product.name.ilike(word_pattern),
                        Product.display_name.ilike(word_pattern),
                        Product.size.ilike(word_pattern),
                        Product.packing.ilike(word_pattern),
                        Product.company_sku.ilike(word_pattern),
                        Product.description.ilike(word_pattern),
                        Product.product_type.ilike(word_pattern),
                        cast(Product.tags, String).ilike(word_pattern),
                    )
                    query = query.where(word_matches_any_field)

            # Order by created_at DESC
            query = query.order_by(Product.created_at.desc())

            result = db.execute(query)
            products = result.scalars().all()

            # Map to response format with totalQuantity
            return [
                {
                    "id": product.id,
                    "name": product.name,
                    "size": product.size,
                    "packing": product.packing,
                    "company_sku": product.company_sku,
                    "default_sale_price": product.default_sale_price,
                    "default_purchase_price": product.default_purchase_price,
                    "display_name": product.display_name,
                    "description": product.description,
                    "mrp": product.mrp,
                    "tags": product.tags,
                    "product_type": product.product_type,
                    "dimensions": product.dimensions,
                    "deleted_at": product.deleted_at,
                    "created_at": product.created_at,
                    "updated_at": product.updated_at,
                    "totalQuantity": sum(
                        cp.quantity for cp in product.containers if cp.deleted_at is None
                    ),
                }
                for product in products
            ]
        return await run_db(_find_all)

    @staticmethod
    async def find_one(product_id: int) -> dict:
        """
        Find a single product by id with containers and logs.
        Optimized: Uses selectinload to eagerly load relationships.

        Args:
            product_id: ID of the product to find

        Returns:
            Product with containers and logs

        Raises:
            NotFoundError: If product not found or is soft-deleted
        """
        def _find_one(db: Session) -> dict:
            # Build query with eager loading for all relationships
            query = (
                select(Product)
                .where(Product.id == product_id, Product.deleted_at.is_(None))
                .options(
                    selectinload(Product.containers).selectinload(ContainerProduct.container),
                    selectinload(Product.logs).selectinload(InventoryLog.container),
                    selectinload(Product.vendor_skus).selectinload(VendorProductSku.vendor),
                    selectinload(Product.images),
                )
            )

            result = db.execute(query)
            product = result.scalar_one_or_none()

            if not product:
                raise NotFoundError("Product", product_id)

            # Filter out soft-deleted containers and logs
            active_containers = [
                cp
                for cp in product.containers
                if cp.deleted_at is None
                and cp.container
                and cp.container.deleted_at is None
            ]

            active_logs = [log for log in product.logs if log.deleted_at is None]
            
            # Filter out soft-deleted vendor SKUs
            active_vendor_skus = [vs for vs in product.vendor_skus if vs.deleted_at is None]

            # Filter out soft-deleted images (ordered by sort_order already via relationship)
            active_images = [img for img in product.images if img.deleted_at is None]

            # Sort logs by created_at DESC
            active_logs.sort(key=lambda x: x.created_at, reverse=True)

            # Map to response format
            return {
                "id": product.id,
                "name": product.name,
                "size": product.size,
                "packing": product.packing,
                "company_sku": product.company_sku,
                "default_sale_price": product.default_sale_price,
                "default_purchase_price": product.default_purchase_price,
                "display_name": product.display_name,
                "description": product.description,
                "mrp": product.mrp,
                "tags": product.tags,
                "product_type": product.product_type,
                "dimensions": product.dimensions,
                "deleted_at": product.deleted_at,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
                "containers": [
                    {
                        "container": cp.container,
                        "quantity": cp.quantity,
                    }
                    for cp in active_containers
                ],
                "logs": [
                    {
                        "id": log.id,
                        "quantity": log.quantity,
                        "action": log.action,
                        "container": (
                            {
                                "id": log.container.id if log.container else None,
                                "name": log.container.name if log.container else None,
                            }
                            if log.container and log.container.deleted_at is None
                            else None
                        ),
                        "created_at": log.created_at,
                    }
                    for log in active_logs
                ],
                "vendor_skus": [
                    {
                        "vendor_id": vs.vendor_id,
                        "vendor_name": vs.vendor.name,
                        "vendor_sku": vs.vendor_sku,
                    }
                    for vs in active_vendor_skus
                ],
                "images": [
                    {
                        "id": img.id,
                        "url": img.url,
                        "thumb_url": img.thumb_url,
                        "sort_order": img.sort_order,
                    }
                    for img in active_images
                ],
            }
        return await run_db(_find_one)

    @staticmethod
    async def add_images(product_id: int, files_data: list[tuple[bytes, str, str]]) -> list[dict]:
        """
        Upload images for a product. Validates product exists and image count limit.
        files_data: list of (bytes, content_type, filename).
        Returns list of ProductImageResponse-like dicts.
        """
        from app.core.gcs_storage import upload_product_image
        from app.core.exceptions import ValidationError

        MAX_IMAGES = 15
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
        ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

        def _add(db: Session) -> list[dict]:
            result = db.execute(select(Product).where(Product.id == product_id, Product.deleted_at.is_(None)))
            product = result.scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", product_id)
            existing = db.execute(select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.deleted_at.is_(None)))
            current_count = len(existing.scalars().all())
            if current_count + len(files_data) > MAX_IMAGES:
                raise ValidationError(f"Product cannot have more than {MAX_IMAGES} images.")
            created = []
            next_order = current_count
            for image_bytes, content_type, filename in files_data:
                if len(image_bytes) > MAX_FILE_SIZE:
                    raise ValidationError("File size exceeds 10 MB limit.")
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ValidationError("Only image/jpeg, image/png, image/webp are allowed.")
                storage_key, url, thumb_url = upload_product_image(product_id, image_bytes, content_type, filename or "image.jpg")
                img = ProductImage(
                    product_id=product_id,
                    drive_file_id=storage_key,
                    url=url,
                    thumb_url=thumb_url,
                    sort_order=next_order,
                )
                db.add(img)
                db.flush()
                db.refresh(img)
                created.append({"id": img.id, "url": img.url, "thumb_url": img.thumb_url, "sort_order": img.sort_order})
                next_order += 1
            return created
        return await run_db(_add)

    @staticmethod
    async def copy_images_from(product_id: int, source_product_id: int, image_ids: list[int] | None = None) -> list[dict]:
        """Copy images from source product to current product. If image_ids given, copy only those; else copy all."""
        from app.core.exceptions import ValidationError

        MAX_IMAGES = 15

        def _copy(db: Session) -> list[dict]:
            result = db.execute(select(Product).where(Product.id == product_id, Product.deleted_at.is_(None)))
            product = result.scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", product_id)
            src_result = db.execute(select(Product).where(Product.id == source_product_id, Product.deleted_at.is_(None)))
            source = src_result.scalar_one_or_none()
            if not source:
                raise NotFoundError("Product", source_product_id)
            if product_id == source_product_id:
                raise ValidationError("Cannot copy images from the same product.")
            existing = db.execute(select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.deleted_at.is_(None)))
            current_count = len(existing.scalars().all())
            query = (
                select(ProductImage)
                .where(ProductImage.product_id == source_product_id, ProductImage.deleted_at.is_(None))
                .order_by(ProductImage.sort_order)
            )
            if image_ids is not None:
                if not image_ids:
                    return []
                query = query.where(ProductImage.id.in_(image_ids))
            src_images = db.execute(query).scalars().all()
            if current_count + len(src_images) > MAX_IMAGES:
                raise ValidationError(f"Product cannot have more than {MAX_IMAGES} images.")
            created = []
            for idx, src in enumerate(src_images):
                img = ProductImage(
                    product_id=product_id,
                    drive_file_id=src.drive_file_id,
                    url=src.url,
                    thumb_url=src.thumb_url,
                    sort_order=current_count + idx,
                )
                db.add(img)
                db.flush()
                db.refresh(img)
                created.append({"id": img.id, "url": img.url, "thumb_url": img.thumb_url, "sort_order": img.sort_order})
            return created
        return await run_db(_copy)

    @staticmethod
    async def delete_image(product_id: int, image_id: int) -> None:
        """Delete one product image. Remove from GCS only if no other row references the blob."""
        from app.core.gcs_storage import delete_file

        def _delete(db: Session) -> None:
            result = db.execute(
                select(ProductImage).where(
                    ProductImage.id == image_id,
                    ProductImage.product_id == product_id,
                    ProductImage.deleted_at.is_(None),
                )
            )
            img = result.scalar_one_or_none()
            if not img:
                raise NotFoundError("ProductImage", image_id)
            storage_key = img.drive_file_id
            db.delete(img)
            db.flush()
            # Refcount: only delete from GCS if no other ProductImage references this blob
            other = db.execute(select(ProductImage).where(ProductImage.drive_file_id == storage_key)).scalars().all()
            if not other:
                delete_file(storage_key)
        await run_db(_delete)

    @staticmethod
    async def reorder_images(product_id: int, order: list[int]) -> None:
        """Update sort_order for product images. order is list of image ids in desired order."""
        from app.core.exceptions import ValidationError

        def _reorder(db: Session) -> None:
            result = db.execute(select(Product).where(Product.id == product_id, Product.deleted_at.is_(None)))
            product = result.scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", product_id)
            images_result = db.execute(select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.deleted_at.is_(None)))
            images = {img.id: img for img in images_result.scalars().all()}
            if set(order) != set(images.keys()):
                raise ValidationError("Order must contain exactly the same image ids as the product.")
            for idx, img_id in enumerate(order):
                images[img_id].sort_order = idx
            db.flush()
        await run_db(_reorder)

    @staticmethod
    async def update(product_id: int, dto: UpdateProductDto) -> Product:
        """
        Update product information.
        Optimized: Single UPDATE query, only updates non-None fields.

        Args:
            product_id: ID of product to update
            dto: DTO containing fields to update

        Returns:
            Updated product instance

        Raises:
            NotFoundError: If product not found
        """
        def _update(db: Session) -> Product:
            # Fetch the product
            result = db.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()

            if not product:
                raise NotFoundError("Product", product_id)

            # Build update dict with only provided values
            update_data = dto.model_dump(exclude_unset=True)

            if update_data:
                for key, value in update_data.items():
                    setattr(product, key, value)

                db.flush()
                db.refresh(product)

            return product
        return await run_db(_update)

    @staticmethod
    async def remove(product_id: int) -> None:
        """
        Soft delete a product by setting deleted_at timestamp.
        Optimized: Single UPDATE query.

        Args:
            product_id: ID of product to soft delete

        Raises:
            NotFoundError: If product not found
        """
        def _remove(db: Session) -> None:
            from datetime import datetime

            result = db.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()

            if not product:
                raise NotFoundError("Product", product_id)

            product.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)

    @staticmethod
    async def validate_products_exist(product_ids: List[int]) -> Dict[int, Product]:
        """
        Validate that all products exist and return them as a dict.
        Single batched query for performance.
        
        Args:
            product_ids: List of product IDs to validate
            
        Returns:
            Dictionary mapping product_id to Product entity
            
        Raises:
            NotFoundError: If any product not found
        """
        def _validate(db: Session) -> Dict[int, Product]:
            if not product_ids:
                return {}
                
            # Batch fetch all products in single query
            products_query = select(Product).where(
                Product.id.in_(product_ids),
                Product.deleted_at.is_(None)
            )
            products_result = db.execute(products_query)
            products = products_result.scalars().all()

            # Validate all products found
            if len(products) != len(set(product_ids)):
                found_ids = {p.id for p in products}
                missing_ids = set(product_ids) - found_ids
                raise NotFoundError("Products", list(missing_ids))

            # Return as dict for O(1) lookup
            return {p.id: p for p in products}
        return await run_db(_validate)
