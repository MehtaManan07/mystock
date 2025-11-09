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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str
    role: Role
    contact_info: Optional[str] = None

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    user: UserResponse
    token: TokenResponse

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    user: UserResponse
    token: TokenResponse

    class Config:
        from_attributes = True
