"""
User DTOs (Data Transfer Objects) - equivalent to NestJS DTOs
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from .models import Role


class UpdateUserDto(BaseModel):
    """DTO for updating user information"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Response model for User entity"""

    id: int
    username: str
    name: str
    role: Role
    contact_info: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

