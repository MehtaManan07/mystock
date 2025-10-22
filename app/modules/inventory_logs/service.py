"""
InventoryLogService - FastAPI equivalent of NestJS InventoryLogService.
Handles inventory log creation and retrieval with optimized queries.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import InventoryLog
from .schemas import CreateInventoryLogDto, CreateInventoryLogBulkDto


class InventoryLogService:
    """
    Inventory log service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    """

    @staticmethod
    async def create_log(db: AsyncSession, dto: CreateInventoryLogDto) -> InventoryLog:
        """
        Create a single inventory log.
        Optimized: Single INSERT query with eager loading.

        Args:
            db: Database session
            dto: Inventory log creation data

        Returns:
            Created inventory log with related product and container
        """
        log = InventoryLog(**dto.model_dump())
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log

    @staticmethod
    async def create_logs_bulk(
        db: AsyncSession, dtos: CreateInventoryLogBulkDto
    ) -> List[InventoryLog]:
        """
        Create multiple inventory logs in bulk.
        Optimized: Single bulk INSERT + single bulk SELECT instead of N refreshes.

        Args:
            db: Database session
            dtos: Bulk inventory log creation data

        Returns:
            List of created inventory logs
        """
        logs = [InventoryLog(**item.model_dump()) for item in dtos.data]
        db.add_all(logs)
        await db.flush()

        # Optimization: Collect IDs and fetch in single query
        log_ids = [log.id for log in logs]

        # Single SELECT to refresh all logs at once with eager loading
        result = await db.execute(
            select(InventoryLog)
            .where(InventoryLog.id.in_(log_ids))
            .options(
                selectinload(InventoryLog.product),
                selectinload(InventoryLog.container),
            )
        )
        refreshed_logs = result.scalars().all()

        # Return in original order
        id_to_log = {log.id: log for log in refreshed_logs}
        return [id_to_log[log_id] for log_id in log_ids]

    @staticmethod
    async def get_logs_for_product(db: AsyncSession, product_id: int) -> List[InventoryLog]:
        """
        Get all inventory logs for a specific product.
        Optimized: Single SELECT with eager loading, ordered by created_at DESC.

        Args:
            db: Database session
            product_id: Product ID to filter by

        Returns:
            List of inventory logs for the product, ordered by newest first
        """
        query = (
            select(InventoryLog)
            .where(
                InventoryLog.product_id == product_id,
                InventoryLog.deleted_at.is_(None),
            )
            .options(
                selectinload(InventoryLog.product),
                selectinload(InventoryLog.container),
            )
            .order_by(InventoryLog.created_at.desc())
        )

        result = await db.execute(query)
        logs = result.scalars().all()
        return list(logs)

    @staticmethod
    async def get_logs_for_container(
        db: AsyncSession, container_id: int
    ) -> List[InventoryLog]:
        """
        Get all inventory logs for a specific container.
        Optimized: Single SELECT with eager loading, ordered by created_at DESC.

        Args:
            db: Database session
            container_id: Container ID to filter by

        Returns:
            List of inventory logs for the container, ordered by newest first
        """
        query = (
            select(InventoryLog)
            .where(
                InventoryLog.container_id == container_id,
                InventoryLog.deleted_at.is_(None),
            )
            .options(
                selectinload(InventoryLog.product),
                selectinload(InventoryLog.container),
            )
            .order_by(InventoryLog.created_at.desc())
        )

        result = await db.execute(query)
        logs = result.scalars().all()
        return list(logs)

    @staticmethod
    async def get_all_logs(db: AsyncSession) -> List[InventoryLog]:
        """
        Get all inventory logs.
        Optimized: Single SELECT with eager loading, ordered by created_at DESC.

        Args:
            db: Database session

        Returns:
            List of all inventory logs, ordered by newest first
        """
        query = (
            select(InventoryLog)
            .where(InventoryLog.deleted_at.is_(None))
            .options(
                selectinload(InventoryLog.product),
                selectinload(InventoryLog.container),
            )
            .order_by(InventoryLog.created_at.desc())
        )

        result = await db.execute(query)
        logs = result.scalars().all()
        return list(logs)

