"""
ProductService - FastAPI equivalent of NestJS ProductService.
Optimized queries with eager loading for relationships.
"""

from typing import List, Optional, Dict
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError

from .schemas import CreateProductDto, CreateProductBulkDto, UpdateProductDto
from .models import Product
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog


class ProductService:
    """
    Product service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    """

    @staticmethod
    async def create(db: AsyncSession, dto: CreateProductDto) -> Product:
        """
        Create a new product.

        Args:
            dto: Product creation data

        Returns:
            Created product instance
        """
        product = Product(name=dto.name, size=dto.size, packing=dto.packing)
        db.add(product)
        await db.flush()
        await db.refresh(product)
        return product

    @staticmethod
    async def bulk_create(
        db: AsyncSession, data: CreateProductBulkDto
    ) -> List[Product]:
        """
        Bulk create products.
        Optimized: Single bulk INSERT + single bulk SELECT instead of N refreshes.

        Args:
            data: Bulk product creation data with list of products

        Returns:
            List of created product instances
        """
        products = [
            Product(name=item.name, size=item.size, packing=item.packing)
            for item in data.data
        ]
        db.add_all(products)
        await db.flush()

        # Optimization: Instead of N refresh calls, collect IDs and fetch in single query
        product_ids = [product.id for product in products]
        
        # Single SELECT to refresh all products at once
        result = await db.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        refreshed_products = result.scalars().all()
        
        # Return in original order
        id_to_product = {p.id: p for p in refreshed_products}
        return [id_to_product[pid] for pid in product_ids]

    @staticmethod
    async def find_all(db: AsyncSession, search: Optional[str] = None) -> List[dict]:
        """
        Find all products with optional search filter.
        Includes total quantity from containers.
        Optimized: Uses selectinload to prevent N+1 queries.

        Args:
            search: Optional search string to filter by name, size, or packing

        Returns:
            List of products with totalQuantity computed from containers
        """
        # Build query with eager loading
        query = (
            select(Product)
            .where(Product.deleted_at.is_(None))
            .options(
                selectinload(Product.containers).selectinload(ContainerProduct.container)
            )
        )

        # Add search filter if provided
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.size.ilike(search_pattern),
                    Product.packing.ilike(search_pattern),
                )
            )

        # Order by created_at DESC
        query = query.order_by(Product.created_at.desc())

        result = await db.execute(query)
        products = result.scalars().all()

        # Map to response format with totalQuantity
        return [
            {
                "id": product.id,
                "name": product.name,
                "size": product.size,
                "packing": product.packing,
                "deleted_at": product.deleted_at,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
                "totalQuantity": sum(
                    cp.quantity for cp in product.containers if cp.deleted_at is None
                ),
            }
            for product in products
        ]

    @staticmethod
    async def find_one(db: AsyncSession, product_id: int) -> dict:
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
        # Build query with eager loading for all relationships
        query = (
            select(Product)
            .where(Product.id == product_id, Product.deleted_at.is_(None))
            .options(
                selectinload(Product.containers).selectinload(ContainerProduct.container),
                selectinload(Product.logs).selectinload(InventoryLog.container),
            )
        )

        result = await db.execute(query)
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

        # Sort logs by created_at DESC
        active_logs.sort(key=lambda x: x.created_at, reverse=True)

        # Map to response format
        return {
            "id": product.id,
            "name": product.name,
            "size": product.size,
            "packing": product.packing,
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
        }

    @staticmethod
    async def update(
        db: AsyncSession, product_id: int, dto: UpdateProductDto
    ) -> Product:
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
        # Fetch the product
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()

        if not product:
            raise NotFoundError("Product", product_id)

        # Build update dict with only provided values
        update_data = dto.model_dump(exclude_unset=True)

        if update_data:
            for key, value in update_data.items():
                setattr(product, key, value)

            await db.flush()
            await db.refresh(product)

        return product

    @staticmethod
    async def remove(db: AsyncSession, product_id: int) -> None:
        """
        Soft delete a product by setting deleted_at timestamp.
        Optimized: Single UPDATE query.

        Args:
            product_id: ID of product to soft delete

        Raises:
            NotFoundError: If product not found
        """
        from datetime import datetime

        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()

        if not product:
            raise NotFoundError("Product", product_id)

        product.deleted_at = datetime.utcnow()
        await db.flush()

    @staticmethod
    async def validate_products_exist(
        db: AsyncSession, product_ids: List[int]
    ) -> Dict[int, Product]:
        """
        Validate that all products exist and return them as a dict.
        Single batched query for performance.
        
        Args:
            db: Database session
            product_ids: List of product IDs to validate
            
        Returns:
            Dictionary mapping product_id to Product entity
            
        Raises:
            NotFoundError: If any product not found
        """
        if not product_ids:
            return {}
            
        # Batch fetch all products in single query
        products_query = select(Product).where(
            Product.id.in_(product_ids),
            Product.deleted_at.is_(None)
        )
        products_result = await db.execute(products_query)
        products = products_result.scalars().all()

        # Validate all products found
        if len(products) != len(set(product_ids)):
            found_ids = {p.id for p in products}
            missing_ids = set(product_ids) - found_ids
            raise NotFoundError("Products", list(missing_ids))

        # Return as dict for O(1) lookup
        return {p.id: p for p in products}
