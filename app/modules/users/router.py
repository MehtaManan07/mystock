"""
Users Router - FastAPI equivalent of NestJS UsersController.
Demonstrates how to use UsersService with dependency injection.
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.engine import get_db_util
from app.core.response_interceptor import skip_interceptor
from .service import UsersService
from .schemas import UserResponse, UpdateUserDto
from .models import Role

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserResponse])
async def get_all_users(db: AsyncSession = Depends(get_db_util)):
    """Get all users"""
    users = await UsersService.find_all(db)
    return users


@router.get("/role", response_model=List[UserResponse])
async def get_users_by_role(
    roles: List[Role] = Query(..., description="List of roles to filter by"),
    db: AsyncSession = Depends(get_db_util)
):
    """Get users by role(s). Pass multiple roles as query params: ?roles=ADMIN&roles=STAFF"""
    users = await UsersService.find_by_role(db, roles)
    return users


@router.get("/me", response_model=UserResponse)
async def get_current_user(user_id: int, db: AsyncSession = Depends(get_db_util)):
    """
    Get current user profile.
    In production, user_id would come from JWT token/auth middleware.
    """
    user = await UsersService.find_me(db, user_id)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db_util)):
    """Get user by ID (excludes soft-deleted users)"""
    user = await UsersService.find_one(db, user_id)
    return user


@router.get("/{user_id}/assigned-tasks", response_model=UserResponse)
async def get_user_assigned_tasks(
    user_id: int, db: AsyncSession = Depends(get_db_util)
):
    """Get user with assigned tasks"""
    user = await UsersService.find_assigned_tasks(db, user_id)
    return user


@router.patch("/{user_id}")
@skip_interceptor
async def update_user(
    user_id: int, update_dto: UpdateUserDto, db: AsyncSession = Depends(get_db_util)
):
    """Update user information (returns custom response format)"""
    await UsersService.update(db, user_id, update_dto)
    return {"message": "User updated successfully"}


@router.delete("/{user_id}")
@skip_interceptor
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db_util)):
    """Soft delete user (returns custom response format)"""
    await UsersService.remove(db, user_id)
    return {"message": "User deleted successfully"}

