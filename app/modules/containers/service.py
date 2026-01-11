"""
ContainerService - FastAPI equivalent of NestJS ContainerService.
Optimized queries with eager loading for relationships.
"""

import re
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from .models import ContainerType, Container
from .schemas import CreateContainerDto, CreateContainerBulkDto, UpdateContainerDto
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog


def extract_number_from_name(name: str) -> int:
    """Extract numeric value from container name for sorting."""
    # Extract all digits from the name
    digits = re.sub(r'\D', '', name)
    return int(digits) if digits else 0


class ContainerService:
    """
    Container service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    """

    @staticmethod
    async def create(db: AsyncSession, dto: CreateContainerDto) -> Container:
        """
        Create a new container.

        Args:
            dto: Container creation data

        Returns:
            Created container instance
        """
        container = Container(name=dto.name, type=ContainerType(dto.type))
        db.add(container)
        await db.flush()
        await db.refresh(container)
        return container

    @staticmethod
    async def bulk_create(
        db: AsyncSession, data: CreateContainerBulkDto
    ) -> List[Container]:
        """
        Bulk create containers.
        Optimized: Single bulk INSERT + single bulk SELECT instead of N refreshes.

        Args:
            data: Bulk container creation data with list of containers

        Returns:
            List of created container instances
        """
        containers = [
            Container(name=item.name, type=ContainerType(item.type))
            for item in data.data
        ]
        db.add_all(containers)
        await db.flush()

        # Optimization: Instead of N refresh calls, collect IDs and fetch in single query
        container_ids = [container.id for container in containers]

        # Single SELECT to refresh all containers at once
        result = await db.execute(
            select(Container).where(Container.id.in_(container_ids))
        )
        refreshed_containers = result.scalars().all()

        # Return in original order
        id_to_container = {c.id: c for c in refreshed_containers}
        return [id_to_container[cid] for cid in container_ids]

    @staticmethod
    async def find_all(db: AsyncSession, search: Optional[str] = None) -> List[dict]:
        """
        Find all containers with optional search filter.
        Includes product count from container_products.
        Optimized: Uses selectinload to prevent N+1 queries.

        Sorting: Extracts numeric values from container names and sorts DESC.
        Done in Python for SQLite compatibility.

        Args:
            search: Optional search string to filter by name

        Returns:
            List of containers with productCount
        """
        # Build base query with eager loading
        query = (
            select(Container)
            .where(Container.deleted_at.is_(None))
            .options(selectinload(Container.contents))
        )

        # Add search filter if provided
        if search:
            search_pattern = f"%{search}%"
            query = query.where(Container.name.ilike(search_pattern))

        result = await db.execute(query)
        containers = list(result.scalars().all())
        
        # Sort in Python: Extract numbers from name and sort DESC
        # This is SQLite-compatible (no regexp_replace function needed)
        containers.sort(key=lambda c: extract_number_from_name(c.name), reverse=True)

        # Map to response format with productCount
        return [
            {
                "id": container.id,
                "name": container.name,
                "type": container.type.value,
                "deleted_at": container.deleted_at,
                "created_at": container.created_at,
                "updated_at": container.updated_at,
                "productCount": sum(
                    1 for cp in container.contents if cp.deleted_at is None
                ),
            }
            for container in containers
        ]

    @staticmethod
    async def find_one_formatted(db: AsyncSession, container_id: int) -> dict:
        """
        Find a single container by id with products and logs.
        Optimized: Uses selectinload to eagerly load relationships.

        Args:
            container_id: ID of the container to find

        Returns:
            Container with products and logs

        Raises:
            NotFoundError: If container not found or is soft-deleted
        """
        # Build query with eager loading for all relationships
        query = (
            select(Container)
            .where(Container.id == container_id, Container.deleted_at.is_(None))
            .options(
                selectinload(Container.contents).selectinload(ContainerProduct.product),
                selectinload(Container.logs).selectinload(InventoryLog.product),
            )
        )

        result = await db.execute(query)
        container = result.scalar_one_or_none()

        if not container:
            raise NotFoundError("Container", container_id)

        # Filter out soft-deleted contents and products
        active_contents = [
            cp
            for cp in container.contents
            if cp.deleted_at is None and cp.product and cp.product.deleted_at is None
        ]

        # Filter out soft-deleted logs and products
        active_logs = [
            log
            for log in container.logs
            if log.deleted_at is None and log.product and log.product.deleted_at is None
        ]

        # Sort logs by created_at DESC
        active_logs.sort(key=lambda x: x.created_at, reverse=True)

        # Map to response format
        return {
            "id": container.id,
            "name": container.name,
            "type": container.type.value,
            "deleted_at": container.deleted_at,
            "created_at": container.created_at,
            "updated_at": container.updated_at,
            "products": [
                {
                    "product": cp.product,
                    "quantity": cp.quantity,
                }
                for cp in active_contents
            ],
            "logs": [
                {
                    "id": log.id,
                    "quantity": log.quantity,
                    "action": log.action,
                    "product": (
                        {
                            "id": log.product.id,
                            "name": log.product.name,
                        }
                        if log.product
                        else None
                    ),
                    "created_at": log.created_at,
                }
                for log in active_logs
            ],
        }

    @staticmethod
    async def update(
        db: AsyncSession, container_id: int, dto: UpdateContainerDto
    ) -> Container:
        """
        Update container information.
        Optimized: Single UPDATE query, only updates non-None fields.

        Args:
            container_id: ID of container to update
            dto: DTO containing fields to update

        Returns:
            Updated container instance

        Raises:
            NotFoundError: If container not found
        """
        # Fetch the container
        result = await db.execute(select(Container).where(Container.id == container_id))
        container = result.scalar_one_or_none()

        if not container:
            raise NotFoundError("Container", container_id)

        # Build update dict with only provided values
        update_data = dto.model_dump(exclude_unset=True)

        if update_data:
            for key, value in update_data.items():
                # Handle enum conversion for type field
                if key == "type" and value is not None:
                    setattr(container, key, ContainerType(value))
                else:
                    setattr(container, key, value)

            await db.flush()
            await db.refresh(container)

        return container

    @staticmethod
    async def remove(db: AsyncSession, container_id: int) -> None:
        """
        Soft delete a container by setting deleted_at timestamp.
        Optimized: Single UPDATE query.

        Args:
            container_id: ID of container to soft delete

        Raises:
            NotFoundError: If container not found
        """
        from datetime import datetime

        result = await db.execute(select(Container).where(Container.id == container_id))
        container = result.scalar_one_or_none()

        if not container:
            raise NotFoundError("Container", container_id)

        container.deleted_at = datetime.utcnow()
        await db.flush()
