"""
InventoryLogService - FastAPI equivalent of NestJS InventoryLogService.
Handles inventory log creation and retrieval with optimized queries.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db.engine import run_db
from .models import InventoryLog
from .schemas import CreateInventoryLogDto, CreateInventoryLogBulkDto


class InventoryLogService:
    """
    Inventory log service with optimized database queries.
    All methods use run_db() for thread-safe Turso operations.
    """

    @staticmethod
    async def create_log(dto: CreateInventoryLogDto) -> InventoryLog:
        """
        Create a single inventory log.
        Optimized: Single INSERT query with eager loading.

        Args:
            dto: Inventory log creation data

        Returns:
            Created inventory log with related product and container
        """
        def _create_log(db: Session) -> InventoryLog:
            log = InventoryLog(**dto.model_dump())
            db.add(log)
            db.flush()
            db.refresh(log)
            return log
        return await run_db(_create_log)

    @staticmethod
    async def create_logs_bulk(dtos: CreateInventoryLogBulkDto) -> List[InventoryLog]:
        """
        Create multiple inventory logs in bulk.
        Optimized: Single bulk INSERT + single bulk SELECT instead of N refreshes.

        Args:
            dtos: Bulk inventory log creation data

        Returns:
            List of created inventory logs
        """
        def _create_logs_bulk(db: Session) -> List[InventoryLog]:
            logs = [InventoryLog(**item.model_dump()) for item in dtos.data]
            db.add_all(logs)
            db.flush()

            # Optimization: Collect IDs and fetch in single query
            log_ids = [log.id for log in logs]

            # Single SELECT to refresh all logs at once with eager loading
            result = db.execute(
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
        return await run_db(_create_logs_bulk)

    @staticmethod
    async def get_logs_for_product(product_id: int) -> List[InventoryLog]:
        """
        Get all inventory logs for a specific product.
        Optimized: Single SELECT with eager loading, ordered by created_at DESC.

        Args:
            product_id: Product ID to filter by

        Returns:
            List of inventory logs for the product, ordered by newest first
        """
        def _get_logs_for_product(db: Session) -> List[InventoryLog]:
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

            result = db.execute(query)
            logs = result.scalars().all()
            return list(logs)
        return await run_db(_get_logs_for_product)

    @staticmethod
    async def get_logs_for_container(container_id: int) -> List[InventoryLog]:
        """
        Get all inventory logs for a specific container.
        Optimized: Single SELECT with eager loading, ordered by created_at DESC.

        Args:
            container_id: Container ID to filter by

        Returns:
            List of inventory logs for the container, ordered by newest first
        """
        def _get_logs_for_container(db: Session) -> List[InventoryLog]:
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

            result = db.execute(query)
            logs = result.scalars().all()
            return list(logs)
        return await run_db(_get_logs_for_container)

    @staticmethod
    async def get_all_logs() -> List[InventoryLog]:
        """
        Get all inventory logs.
        Optimized: Single SELECT with eager loading, ordered by created_at DESC.

        Returns:
            List of all inventory logs, ordered by newest first
        """
        def _get_all_logs(db: Session) -> List[InventoryLog]:
            query = (
                select(InventoryLog)
                .where(InventoryLog.deleted_at.is_(None))
                .options(
                    selectinload(InventoryLog.product),
                    selectinload(InventoryLog.container),
                )
                .order_by(InventoryLog.created_at.desc())
            )

            result = db.execute(query)
            logs = result.scalars().all()
            return list(logs)
        return await run_db(_get_all_logs)
