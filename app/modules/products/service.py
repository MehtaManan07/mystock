"""
ProductService - FastAPI equivalent of NestJS ProductService.
Optimized queries with eager loading for relationships.
"""

from typing import List, Optional, Dict
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError

from .schemas import CreateProductDto, CreateProductBulkDto, UpdateProductDto
from .models import Product
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

            # Add search filter if provided
            # Split search into words and require ALL words to match in name field
            if search:
                words = search.strip().split()
                for word in words:
                    word_pattern = f"%{word}%"
                    query = query.where(Product.name.ilike(word_pattern))

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
            }
        return await run_db(_find_one)

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
