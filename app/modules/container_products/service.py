"""
ContainerProductService - FastAPI equivalent of NestJS ContainerProductService.
Handles complex transaction logic with pessimistic locking and inventory tracking.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, func, text, tuple_
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
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
    All methods use run_db() for thread-safe Turso operations.
    """

    @staticmethod
    async def set_products_in_container(payload: CreateContainerProductDto) -> None:
        """
        Set products in a container with transaction safety.
        This is the main business logic method that:
        - Fetches existing records within a transaction
        - Calculates deltas and creates audit logs
        - Updates/creates/soft-deletes container-product relationships
        
        Concurrency: Transaction isolation handles
        concurrent access safely for our expected 5-10 user load.

        Args:
            payload: DTO containing containerId and items with productId + quantity

        Raises:
            ValidationError: If quantity is negative
        """
        def _set_products_in_container(db: Session) -> None:
            container_id = payload.containerId
            items = payload.items

            # Extract product IDs
            product_ids = [item.productId for item in items]

            # Get existing records within transaction
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
            result = db.execute(query)
            existing = result.scalars().all()
            existing_map = {f"{entry.container_id}-{entry.product_id}": entry for entry in existing}

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
                        # Any quantity update counts as verification
                        record.last_verified_at = datetime.utcnow()
                        to_save.append(record)
                else:
                    # Record doesn't exist
                    if quantity == 0:
                        # Skip - no need to create a record with 0 quantity
                        continue

                    # Create new record with verification timestamp
                    new_entry = ContainerProduct(
                        container_id=container_id,
                        product_id=product_id,
                        quantity=quantity,
                        last_verified_at=datetime.utcnow(),
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
                db.flush()

            if to_soft_delete:
                # Soft deletes are already marked with deleted_at
                db.flush()

            if logs_to_insert:
                db.add_all(logs_to_insert)
                db.flush()
        await run_db(_set_products_in_container)

    @staticmethod
    async def verify_product_location(container_id: int, product_id: int) -> None:
        """
        Mark a product-container location as verified.
        Updates the last_verified_at timestamp without changing quantity.
        
        Args:
            container_id: Container ID
            product_id: Product ID
            
        Raises:
            ValidationError: If the product-container relationship doesn't exist
        """
        def _verify_product_location(db: Session) -> None:
            query = select(ContainerProduct).where(
                ContainerProduct.container_id == container_id,
                ContainerProduct.product_id == product_id,
                ContainerProduct.deleted_at.is_(None),
            )
            
            result = db.execute(query)
            record = result.scalar_one_or_none()
            
            if not record:
                raise ValidationError(
                    f"Product {product_id} not found in container {container_id}"
                )
            
            record.last_verified_at = datetime.utcnow()
            db.flush()
        await run_db(_verify_product_location)

    @staticmethod
    async def get_products_in_container(container_id: int) -> List[ContainerProduct]:
        """
        Get all products in a container.

        Args:
            container_id: Container ID

        Returns:
            List of ContainerProduct with product and container relationships loaded
        """
        def _get_products_in_container(db: Session) -> List[ContainerProduct]:
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

            result = db.execute(query)
            return list(result.scalars().all())
        return await run_db(_get_products_in_container)

    @staticmethod
    async def get_containers_for_product(product_id: int) -> List[ContainerProduct]:
        """
        Get all containers for a product.

        Args:
            product_id: Product ID

        Returns:
            List of ContainerProduct with container and product relationships loaded
        """
        def _get_containers_for_product(db: Session) -> List[ContainerProduct]:
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

            result = db.execute(query)
            return list(result.scalars().all())
        return await run_db(_get_containers_for_product)

    @staticmethod
    async def search_containers_by_sku(sku: str) -> List[ContainerProduct]:
        """
        Search containers by product SKU (name).

        Args:
            sku: Product name to search for (case-insensitive, partial match)

        Returns:
            List of ContainerProduct with container and product relationships loaded
        """
        def _search_containers_by_sku(db: Session) -> List[ContainerProduct]:
            query = (
                select(ContainerProduct)
                .join(ContainerProduct.product)
                .where(Product.name.ilike(f"%{sku}%"))
                .options(
                    selectinload(ContainerProduct.container),
                    selectinload(ContainerProduct.product),
                )
            )

            result = db.execute(query)
            return list(result.scalars().all())
        return await run_db(_search_containers_by_sku)

    @staticmethod
    async def get_total_quantity_of_sku(product_id: int) -> Dict[str, int]:
        """
        Get total quantity of a product across all containers.

        Args:
            product_id: Product ID

        Returns:
            Dictionary with productId and totalQuantity
        """
        def _get_total_quantity_of_sku(db: Session) -> Dict[str, int]:
            query = select(func.sum(ContainerProduct.quantity)).where(
                ContainerProduct.product_id == product_id,
                ContainerProduct.deleted_at.is_(None),
            )

            result = db.execute(query)
            total = result.scalar_one_or_none()

            return {
                "productId": product_id,
                "totalQuantity": int(total) if total else 0,
            }
        return await run_db(_get_total_quantity_of_sku)

    @staticmethod
    async def get_basic_analytics() -> Dict[str, int]:
        """
        Get basic analytics: total products, containers, and quantity.

        Returns:
            Dictionary with totalProducts, totalContainers, totalQuantity
        """
        def _get_basic_analytics(db: Session) -> Dict[str, int]:
            # Count total products
            product_count_query = select(func.count(Product.id)).where(
                Product.deleted_at.is_(None)
            )
            product_result = db.execute(product_count_query)
            total_products = product_result.scalar_one()

            # Count total containers
            container_count_query = select(func.count(Container.id)).where(
                Container.deleted_at.is_(None)
            )
            container_result = db.execute(container_count_query)
            total_containers = container_result.scalar_one()

            # Sum total quantity
            quantity_query = select(func.sum(ContainerProduct.quantity)).where(
                ContainerProduct.deleted_at.is_(None)
            )
            quantity_result = db.execute(quantity_query)
            total_quantity = quantity_result.scalar_one_or_none()

            return {
                "totalProducts": total_products,
                "totalContainers": total_containers,
                "totalQuantity": int(total_quantity) if total_quantity else 0,
            }
        return await run_db(_get_basic_analytics)

    @staticmethod
    async def map_products_to_ids(input_data: List[MapProductInputDto]) -> List[MapProductOutputDto]:
        """
        Map product names and sizes to their IDs.
        Uses raw SQL for efficient bulk lookup.

        Args:
            input_data: List of product name, size, and quantity

        Returns:
            List of productId and quantity mappings
        """
        def _map_products_to_ids(db: Session) -> List[MapProductOutputDto]:
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
            result = db.execute(query_text, values)
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
        return await run_db(_map_products_to_ids)

    @staticmethod
    async def validate_and_get_stock(
        items: List[Tuple[int, int]],  # List of (product_id, container_id) tuples
    ) -> Dict[Tuple[int, int], ContainerProduct]:
        """
        Validate stock availability for multiple product-container pairs.
        Single batched query for performance.
        
        Args:
            items: List of (product_id, container_id) tuples
            
        Returns:
            Dictionary mapping (product_id, container_id) to ContainerProduct entity
            
        Raises:
            ValidationError: If any product not found in specified container
        """
        def _validate_and_get_stock(db: Session) -> Dict[Tuple[int, int], ContainerProduct]:
            if not items:
                return {}
                
            # Batch fetch all ContainerProduct rows in single query
            container_product_query = select(ContainerProduct).where(
                tuple_(ContainerProduct.product_id, ContainerProduct.container_id).in_(items)
            )
            cp_result = db.execute(container_product_query)
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
        return await run_db(_validate_and_get_stock)
