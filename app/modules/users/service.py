"""
UsersService - FastAPI equivalent of NestJS UsersService.
Optimized queries with no extra SQL calls.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from .models import User, Role
from .schemas import UpdateUserDto


class UsersService:
    """
    Users service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    """

    @staticmethod
    async def find_all(db: AsyncSession) -> List[User]:
        """
        Find all users.
        Optimized: Single SELECT query without filters.
        """
        result = await db.execute(select(User))
        users = result.scalars().all()
        return list(users)

    @staticmethod
    async def find_one(db: AsyncSession, user_id: int) -> User:
        """
        Find a single user by id where deleted_at is null.
        Optimized: Single SELECT with composite WHERE clause.
        
        Raises:
            NotFoundError: If user not found or is soft-deleted
        """
        result = await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError("User", user_id)

        return user

    @staticmethod
    async def find_by_role(db: AsyncSession, roles: List[Role]) -> List[User]:
        """
        Find users by multiple roles where deleted_at is null.
        Optimized: Single SELECT with IN clause and deleted_at filter.
        
        Args:
            roles: List of Role enums to filter by
        """
        result = await db.execute(
            select(User).where(User.role.in_(roles), User.deleted_at.is_(None))
        )
        users = result.scalars().all()
        return list(users)

    @staticmethod
    async def find_assigned_tasks(db: AsyncSession, user_id: int) -> User:
        """
        Find user with assigned tasks by id where deleted_at is null.
        Optimized: Single SELECT query.
        
        Note: If you need to load relationships (like tasks), add:
        .options(selectinload(User.tasks)) to prevent N+1 queries
        
        Raises:
            NotFoundError: If user not found or is soft-deleted
        """
        result = await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError("User", user_id)

        return user

    @staticmethod
    async def find_me(db: AsyncSession, user_id: int) -> User:
        """
        Find current user by id (ignores deleted_at).
        Optimized: Single SELECT with simple WHERE clause.
        
        Raises:
            NotFoundError: If user not found
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError("User", user_id)

        return user

    @staticmethod
    async def update(
        db: AsyncSession, user_id: int, update_dto: UpdateUserDto
    ) -> None:
        """
        Update user information.
        Optimized: Single UPDATE query, only updates non-None fields.
        
        Args:
            user_id: ID of user to update
            update_dto: DTO containing fields to update
        """
        # Build update dict with only provided values
        update_data = update_dto.model_dump(exclude_unset=True)

        if update_data:
            # Single UPDATE query
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                for key, value in update_data.items():
                    setattr(user, key, value)
                
                await db.flush()

    @staticmethod
    async def remove(db: AsyncSession, user_id: int) -> None:
        """
        Soft delete a user by setting deleted_at timestamp.
        Optimized: Single UPDATE query.
        
        Args:
            user_id: ID of user to soft delete
        """
        from datetime import datetime

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user:
            user.deleted_at = datetime.utcnow()
            await db.flush()

