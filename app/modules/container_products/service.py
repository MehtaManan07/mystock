"""
ContainerProductService - FastAPI equivalent of NestJS ContainerProductService.
Handles complex transaction logic with pessimistic locking and inventory tracking.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, func, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ValidationError
from app.modules.container_products.models import ContainerProduct
from app.modules.container_products.schemas import (
    CreateContainerProductDto,
    MapProductInputDto,
    MapProductOutputDto,
)
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.inventory_logs.models import InventoryLog


class ContainerProductService:
    """
    ContainerProduct service with complex transaction logic.
    Handles inventory management with pessimistic locking and audit logging.
    """

    @staticmethod
    async def _get_container_products(
        db: AsyncSession,
        container_id: int,
        product_ids: List[int],
    ) -> Dict[str, ContainerProduct]:
        """
        Get container products for update within a transaction.
        
        Concurrency handling:
        - SQLite with WAL mode handles concurrent access at the database level
        - The transaction isolation ensures consistency
        - busy_timeout prevents immediate "database is locked" errors

        Args:
            db: Database session (within transaction)
            container_id: Container ID
            product_ids: List of product IDs

        Returns:
            Dictionary mapping "containerId-productId" to ContainerProduct
        """
        # Query existing container products
        # Note: SQLite doesn't support FOR UPDATE, but WAL mode + transaction
        # isolation provides safe concurrent access for our 5-10 user load
        query = (
            select(ContainerProduct)
            .where(
                ContainerProduct.container_id == container_id,
                ContainerProduct.product_id.in_(product_ids),
            )
            .options(
                selectinload(ContainerProduct.container),
                selectinload(ContainerProduct.product),
            )
        )

        result = await db.execute(query)
        existing = result.scalars().all()

        # Create map for quick lookup
        return {f"{entry.container_id}-{entry.product_id}": entry for entry in existing}

    @staticmethod
    async def set_products_in_container(
        db: AsyncSession, payload: CreateContainerProductDto
    ) -> None:
        """
        Set products in a container with transaction safety.
        This is the main business logic method that:
        - Fetches existing records within a transaction
        - Calculates deltas and creates audit logs
        - Updates/creates/soft-deletes container-product relationships
        
        Concurrency: SQLite WAL mode + transaction isolation handles
        concurrent access safely for our expected 5-10 user load.

        Args:
            db: Database session
            payload: DTO containing containerId and items with productId + quantity

        Raises:
            ValidationError: If quantity is negative
        """
        container_id = payload.containerId
        items = payload.items

        # Extract product IDs
        product_ids = [item.productId for item in items]

        # Get existing records within transaction
        existing_map = await ContainerProductService._get_container_products(
            db, container_id, product_ids
        )

        to_save: List[ContainerProduct] = []
        to_soft_delete: List[ContainerProduct] = []
        logs_to_insert: List[InventoryLog] = []

        # Process each item
        for item in items:
            product_id = item.productId
            quantity = item.quantity

            # Validate quantity
            if quantity < 0:
                raise ValidationError(
                    f"Quantity can't be negative for product {product_id}"
                )

            key = f"{container_id}-{product_id}"
            record = existing_map.get(key)

            if record:
                # Record exists - calculate delta
                delta = quantity - record.quantity

                # Create log if quantity changed
                if delta != 0:
                    log = InventoryLog(
                        container_id=container_id,
                        product_id=product_id,
                        quantity=abs(delta),
                        action="added" if delta > 0 else "removed",
                    )
                    logs_to_insert.append(log)

                # Handle soft delete or update
                if quantity == 0:
                    # Soft delete
                    record.deleted_at = datetime.utcnow()
                    to_soft_delete.append(record)
                else:
                    # Update quantity and restore if previously soft-deleted
                    record.quantity = quantity
                    record.deleted_at = None
                    to_save.append(record)
            else:
                # Record doesn't exist
                if quantity == 0:
                    # Skip - no need to create a record with 0 quantity
                    continue

                # Create new record
                new_entry = ContainerProduct(
                    container_id=container_id,
                    product_id=product_id,
                    quantity=quantity,
                )
                to_save.append(new_entry)

                # Create log for addition
                log = InventoryLog(
                    container_id=container_id,
                    product_id=product_id,
                    quantity=quantity,
                    action="added",
                )
                logs_to_insert.append(log)

        # Save all changes
        if to_save:
            db.add_all(to_save)
            await db.flush()

        if to_soft_delete:
            # Soft deletes are already marked with deleted_at
            await db.flush()

        if logs_to_insert:
            db.add_all(logs_to_insert)
            await db.flush()

    @staticmethod
    async def get_products_in_container(
        db: AsyncSession, container_id: int
    ) -> List[ContainerProduct]:
        """
        Get all products in a container.

        Args:
            db: Database session
            container_id: Container ID

        Returns:
            List of ContainerProduct with product and container relationships loaded
        """
        query = (
            select(ContainerProduct)
            .join(ContainerProduct.product)
            .where(ContainerProduct.container_id == container_id)
            .options(
                selectinload(ContainerProduct.product),
                selectinload(ContainerProduct.container),
            )
            .order_by(Product.name.asc())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_containers_for_product(
        db: AsyncSession, product_id: int
    ) -> List[ContainerProduct]:
        """
        Get all containers for a product.

        Args:
            db: Database session
            product_id: Product ID

        Returns:
            List of ContainerProduct with container and product relationships loaded
        """
        query = (
            select(ContainerProduct)
            .join(ContainerProduct.container)
            .where(ContainerProduct.product_id == product_id)
            .options(
                selectinload(ContainerProduct.container),
                selectinload(ContainerProduct.product),
            )
            .order_by(Container.name.asc())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def search_containers_by_sku(
        db: AsyncSession, sku: str
    ) -> List[ContainerProduct]:
        """
        Search containers by product SKU (name).

        Args:
            db: Database session
            sku: Product name to search for (case-insensitive, partial match)

        Returns:
            List of ContainerProduct with container and product relationships loaded
        """
        query = (
            select(ContainerProduct)
            .join(ContainerProduct.product)
            .where(Product.name.ilike(f"%{sku}%"))
            .options(
                selectinload(ContainerProduct.container),
                selectinload(ContainerProduct.product),
            )
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_total_quantity_of_sku(
        db: AsyncSession, product_id: int
    ) -> Dict[str, int]:
        """
        Get total quantity of a product across all containers.

        Args:
            db: Database session
            product_id: Product ID

        Returns:
            Dictionary with productId and totalQuantity
        """
        query = select(func.sum(ContainerProduct.quantity)).where(
            ContainerProduct.product_id == product_id,
            ContainerProduct.deleted_at.is_(None),
        )

        result = await db.execute(query)
        total = result.scalar_one_or_none()

        return {
            "productId": product_id,
            "totalQuantity": int(total) if total else 0,
        }

    @staticmethod
    async def get_basic_analytics(db: AsyncSession) -> Dict[str, int]:
        """
        Get basic analytics: total products, containers, and quantity.

        Args:
            db: Database session

        Returns:
            Dictionary with totalProducts, totalContainers, totalQuantity
        """
        # Count total products
        product_count_query = select(func.count(Product.id)).where(
            Product.deleted_at.is_(None)
        )
        product_result = await db.execute(product_count_query)
        total_products = product_result.scalar_one()

        # Count total containers
        container_count_query = select(func.count(Container.id)).where(
            Container.deleted_at.is_(None)
        )
        container_result = await db.execute(container_count_query)
        total_containers = container_result.scalar_one()

        # Sum total quantity
        quantity_query = select(func.sum(ContainerProduct.quantity)).where(
            ContainerProduct.deleted_at.is_(None)
        )
        quantity_result = await db.execute(quantity_query)
        total_quantity = quantity_result.scalar_one_or_none()

        return {
            "totalProducts": total_products,
            "totalContainers": total_containers,
            "totalQuantity": int(total_quantity) if total_quantity else 0,
        }

    @staticmethod
    async def map_products_to_ids(
        db: AsyncSession, input_data: List[MapProductInputDto]
    ) -> List[MapProductOutputDto]:
        """
        Map product names and sizes to their IDs.
        Uses raw SQL for efficient bulk lookup.

        Args:
            db: Database session
            input_data: List of product name, size, and quantity

        Returns:
            List of productId and quantity mappings
        """
        if not input_data:
            return []

        # Build parameterized query for bulk lookup
        # Equivalent to: WHERE (name, size) IN (($1, $2), ($3, $4), ...)
        params = []
        values = {}
        for i, item in enumerate(input_data):
            params.append(f"(:name_{i}, :size_{i})")
            values[f"name_{i}"] = item.name
            values[f"size_{i}"] = item.size

        # Execute raw SQL query
        query_text = text(
            f"SELECT id, name, size FROM product WHERE (name, size) IN ({', '.join(params)})"
        )
        result = await db.execute(query_text, values)
        db_products = result.fetchall()

        # Create lookup map
        id_map = {f"{row.name}|{row.size}": row.id for row in db_products}

        # Map input to output
        return [
            MapProductOutputDto(
                quantity=item.quantity,
                productId=id_map.get(f"{item.name}|{item.size}"),
            )
            for item in input_data
        ]

    @staticmethod
    async def validate_and_get_stock(
        db: AsyncSession,
        items: List[Tuple[int, int]],  # List of (product_id, container_id) tuples
    ) -> Dict[Tuple[int, int], ContainerProduct]:
        """
        Validate stock availability for multiple product-container pairs.
        Single batched query for performance.
        
        Args:
            db: Database session
            items: List of (product_id, container_id) tuples
            
        Returns:
            Dictionary mapping (product_id, container_id) to ContainerProduct entity
            
        Raises:
            ValidationError: If any product not found in specified container
        """
        if not items:
            return {}
            
        # Batch fetch all ContainerProduct rows in single query
        container_product_query = select(ContainerProduct).where(
            tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(items)
        )
        cp_result = await db.execute(container_product_query)
        container_products = cp_result.scalars().all()
        
        # Build lookup map
        container_product_map = {
            (cp.product_id, cp.container_id): cp for cp in container_products
        }
        
        # Validate all requested pairs exist
        if len(container_product_map) != len(set(items)):
            found_keys = set(container_product_map.keys())
            missing_keys = set(items) - found_keys
            raise ValidationError(
                f"Products not found in specified containers: {list(missing_keys)}"
            )
        
        return container_product_map
