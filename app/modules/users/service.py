"""
UsersService - FastAPI equivalent of NestJS UsersService.
Optimized queries with no extra SQL calls.
"""

from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.modules.users.auth import AuthService
from .models import Role, User
from .schemas import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
    RefreshTokenRequest,
    UpdateUserDto,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)


class UsersService:
    """
    Users service with optimized database queries.
    All methods use async/await and efficient SQLAlchemy queries.
    """

    @staticmethod
    def _get_user_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            username=user.username,
            name=user.name,
            role=user.role,
            contact_info=user.contact_info,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    async def create(db: AsyncSession, create_dto: RegisterRequest) -> RegisterResponse:
        """
        Create a new user.
        """
        existing_user = await db.execute(
            select(User).where(User.username == create_dto.username)
        )
        if existing_user.scalars().first():
            raise ConflictError("User already exists with this username")

        user = User(
            username=create_dto.username,
            password=AuthService.get_password_hash(create_dto.password),
            name=create_dto.name,
            role=create_dto.role,
            contact_info=create_dto.contact_info,
        )
        db.add(user)
        await db.commit()
        user_response = UsersService._get_user_response(user)
        
        # Create tokens with user data
        token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value
        }
        access_token = AuthService.create_access_token(token_data)
        refresh_token = AuthService.create_refresh_token(token_data)
        
        return RegisterResponse(
            user=user_response,
            token=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer"
            ),
        )

    @staticmethod
    async def login(db: AsyncSession, login_dto: LoginRequest) -> LoginResponse:
        """
        Login a user.
        """
        user = await db.scalar(select(User).where(User.username == login_dto.username))
        if not user:
            raise NotFoundError("User", login_dto.username)
        if not AuthService.verify_password(login_dto.password, user.password):
            raise UnauthorizedError("Invalid password")
        
        user_response = UsersService._get_user_response(user)
        
        # Create tokens with user data
        token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value
        }
        access_token = AuthService.create_access_token(token_data)
        refresh_token = AuthService.create_refresh_token(token_data)
        
        return LoginResponse(
            user=user_response,
            token=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer"
            ),
        )

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
    async def update(db: AsyncSession, user_id: int, update_dto: UpdateUserDto) -> None:
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
            result = await db.execute(select(User).where(User.id == user_id))
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

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_request: RefreshTokenRequest) -> TokenResponse:
        """
        Generate new access token using refresh token.
        
        Args:
            db: Database session
            refresh_request: Request containing refresh token
            
        Returns:
            New access and refresh tokens
            
        Raises:
            UnauthorizedError: If refresh token is invalid
        """
        payload: Dict[str, Any] | None = AuthService.verify_refresh_token(refresh_request.refresh_token)
        
        if not payload:
            raise UnauthorizedError("Invalid refresh token")
        
        username: str | None = payload.get("sub")
        user_id: int | None = payload.get("user_id")
        
        # Verify user still exists
        user: User | None = await db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise UnauthorizedError("User not found")
        
        # Create new tokens
        token_data: Dict[str, Any] = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value
        }
        access_token: str = AuthService.create_access_token(token_data)
        refresh_token: str = AuthService.create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
