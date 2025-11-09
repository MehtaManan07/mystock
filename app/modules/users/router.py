"""
Users Router - FastAPI equivalent of NestJS UsersController.
Demonstrates authentication and authorization with JWT tokens and role-based access control.
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from .service import UsersService
from .schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
    UpdateUserDto,
)
from .models import Role
from .auth import (
    get_current_user,
    TokenData,
    require_admin,
    require_admin_or_manager,
    require_any_role,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    register_dto: RegisterRequest, db: AsyncSession = Depends(get_db_util)
):
    """Register a new user"""
    return await UsersService.create(db, register_dto)


@router.post("/login", response_model=LoginResponse)
async def login_user(login_dto: LoginRequest, db: AsyncSession = Depends(get_db_util)):
    """Login a user and receive JWT tokens"""
    return await UsersService.login(db, login_dto)


@router.get("", response_model=List[UserResponse])
async def get_all_users(
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_manager)
):
    """Get all users (Admin/Manager only)"""
    users = await UsersService.find_all(db)
    return users


@router.get("/role", response_model=List[UserResponse])
async def get_users_by_role(
    roles: List[Role] = Query(..., description="List of roles to filter by"),
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_manager)
):
    """Get users by role(s) (Admin/Manager only). Pass multiple roles as query params: ?roles=ADMIN&roles=STAFF"""
    users = await UsersService.find_by_role(db, roles)
    return users


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get current user profile from JWT token.
    Requires valid authentication token in Authorization header.
    """
    user = await UsersService.find_me(db, current_user.user_id)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_any_role)
):
    """Get user by ID (excludes soft-deleted users) - requires authentication"""
    user = await UsersService.find_one(db, user_id)
    return user


@router.get("/{user_id}/assigned-tasks", response_model=UserResponse)
async def get_user_assigned_tasks(
    user_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin_or_manager)
):
    """Get user with assigned tasks (Admin/Manager only)"""
    user = await UsersService.find_assigned_tasks(db, user_id)
    return user


@router.patch("/{user_id}")
@skip_interceptor
async def update_user(
    user_id: int,
    update_dto: UpdateUserDto,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin)
):
    """Update user information (Admin only)"""
    await UsersService.update(db, user_id, update_dto)
    return {"message": "User updated successfully"}


@router.delete("/{user_id}")
@skip_interceptor
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_util),
    current_user: TokenData = Depends(require_admin)
):
    """Soft delete user (Admin only)"""
    await UsersService.remove(db, user_id)
    return {"message": "User deleted successfully"}
