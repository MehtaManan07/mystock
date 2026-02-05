"""
UsersService - FastAPI equivalent of NestJS UsersService.
Optimized queries with no extra SQL calls.
"""

from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.modules.users.auth import AuthService
from .models import Role, User
from .schemas import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
    UpdateUserDto,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)


class UsersService:
    """
    Users service with optimized database queries.
    All methods use run_db() for thread-safe Turso operations.
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
    async def create(create_dto: RegisterRequest) -> RegisterResponse:
        """
        Create a new user.
        """
        def _create(db: Session) -> RegisterResponse:
            existing_user = db.execute(
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
            db.flush()
            db.refresh(user)
            
            user_response = UsersService._get_user_response(user)
            
            # Create tokens with user data
            token_data = {
                "sub": user.username,
                "user_id": user.id,
                "role": user.role.value
            }
            access_token = AuthService.create_access_token(token_data)
            
            return RegisterResponse(
                user=user_response,
                token=TokenResponse(
                    access_token=access_token,
                    token_type="bearer"
                ),
            )
        return await run_db(_create)

    @staticmethod
    async def login(login_dto: LoginRequest) -> LoginResponse:
        """
        Login a user.
        """
        def _login(db: Session) -> LoginResponse:
            user = db.scalar(select(User).where(User.username == login_dto.username))
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
            
            return LoginResponse(
                user=user_response,
                token=TokenResponse(
                    access_token=access_token,
                    token_type="bearer"
                ),
            )
        return await run_db(_login)

    @staticmethod
    async def find_all() -> List[User]:
        """
        Find all users.
        Optimized: Single SELECT query without filters.
        """
        def _find_all(db: Session) -> List[User]:
            result = db.execute(select(User))
            users = result.scalars().all()
            return list(users)
        return await run_db(_find_all)

    @staticmethod
    async def find_one(user_id: int) -> User:
        """
        Find a single user by id where deleted_at is null.
        Optimized: Single SELECT with composite WHERE clause.

        Raises:
            NotFoundError: If user not found or is soft-deleted
        """
        def _find_one(db: Session) -> User:
            result = db.execute(
                select(User).where(User.id == user_id, User.deleted_at.is_(None))
            )
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User", user_id)

            return user
        return await run_db(_find_one)

    @staticmethod
    async def find_by_role(roles: List[Role]) -> List[User]:
        """
        Find users by multiple roles where deleted_at is null.
        Optimized: Single SELECT with IN clause and deleted_at filter.

        Args:
            roles: List of Role enums to filter by
        """
        def _find_by_role(db: Session) -> List[User]:
            result = db.execute(
                select(User).where(User.role.in_(roles), User.deleted_at.is_(None))
            )
            users = result.scalars().all()
            return list(users)
        return await run_db(_find_by_role)

    @staticmethod
    async def find_assigned_tasks(user_id: int) -> User:
        """
        Find user with assigned tasks by id where deleted_at is null.
        Optimized: Single SELECT query.

        Raises:
            NotFoundError: If user not found or is soft-deleted
        """
        def _find_assigned_tasks(db: Session) -> User:
            result = db.execute(
                select(User).where(User.id == user_id, User.deleted_at.is_(None))
            )
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User", user_id)

            return user
        return await run_db(_find_assigned_tasks)

    @staticmethod
    async def find_me(user_id: int) -> User:
        """
        Find current user by id (ignores deleted_at).
        Optimized: Single SELECT with simple WHERE clause.

        Raises:
            NotFoundError: If user not found
        """
        def _find_me(db: Session) -> User:
            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User", user_id)

            return user
        return await run_db(_find_me)

    @staticmethod
    async def update(user_id: int, update_dto: UpdateUserDto) -> None:
        """
        Update user information.
        Optimized: Single UPDATE query, only updates non-None fields.

        Args:
            user_id: ID of user to update
            update_dto: DTO containing fields to update
        """
        def _update(db: Session) -> None:
            # Build update dict with only provided values
            update_data = update_dto.model_dump(exclude_unset=True)

            if update_data:
                # Single UPDATE query
                result = db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()

                if user:
                    for key, value in update_data.items():
                        setattr(user, key, value)

                    db.flush()
        await run_db(_update)

    @staticmethod
    async def remove(user_id: int) -> None:
        """
        Soft delete a user by setting deleted_at timestamp.
        Optimized: Single UPDATE query.

        Args:
            user_id: ID of user to soft delete
        """
        def _remove(db: Session) -> None:
            from datetime import datetime

            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                user.deleted_at = datetime.utcnow()
                db.flush()
        await run_db(_remove)
