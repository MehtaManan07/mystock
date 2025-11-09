"""
Authentication and Authorization utilities for JWT-based auth.
Provides password hashing, token generation/verification, and user dependency injection.
"""

from typing import Optional, Any, Dict, List, Union
from dataclasses import dataclass
import bcrypt
import jwt
from jwt.exceptions import PyJWTError, ExpiredSignatureError
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import config
from app.core.exceptions import UnauthorizedError


# HTTP Bearer token security scheme
security = HTTPBearer()


@dataclass
class TokenData:
    """Token payload data structure with type safety"""
    user_id: int
    username: str
    role: str


class AuthService:
    """
    Authentication service for user login, registration, and token management.
    """

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hashed password using bcrypt.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        )

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Hash a password using bcrypt with auto-generated salt.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password as string
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token with user data and expiration.
        
        Args:
            data: Dictionary containing user data (user_id, username, role)
            expires_delta: Optional custom expiration time, defaults to config value
            
        Returns:
            Encoded JWT token as string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=config.access_token_expire_minutes
            )
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        encoded_jwt = jwt.encode(
            to_encode, config.secret_key, algorithm=config.algorithm
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token with extended expiration (7 days).
        
        Args:
            data: Dictionary containing user data (user_id, username)
            
        Returns:
            Encoded JWT refresh token as string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=7)
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        encoded_jwt = jwt.encode(
            to_encode, config.secret_key, algorithm=config.algorithm
        )
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Optional[TokenData]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string to verify
            
        Returns:
            TokenData object if valid, None if invalid
        """
        try:
            payload: Dict[str, Any] = jwt.decode(
                token, config.secret_key, algorithms=[config.algorithm]
            )
            user_id: Optional[int] = payload.get("user_id")
            username: Optional[str] = payload.get("sub")
            role: Optional[str] = payload.get("role")
            
            if username is None or user_id is None or role is None:
                return None
                
            return TokenData(user_id=user_id, username=username, role=role)
        except ExpiredSignatureError:
            raise UnauthorizedError("Token has expired")
        except PyJWTError:
            return None

    @staticmethod
    def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a refresh token and extract payload.
        
        Args:
            token: JWT refresh token to verify
            
        Returns:
            Token payload if valid, None if invalid
        """
        try:
            payload: Dict[str, Any] = jwt.decode(
                token, config.secret_key, algorithms=[config.algorithm]
            )
            if payload.get("type") != "refresh":
                return None
            return payload
        except ExpiredSignatureError:
            raise UnauthorizedError("Refresh token has expired")
        except PyJWTError:
            return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        
    Returns:
        TokenData object containing user information
        
    Raises:
        UnauthorizedError: If token is invalid or user not found
    """
    token: str = credentials.credentials
    token_data: Optional[TokenData] = AuthService.verify_token(token)
    
    if token_data is None:
        raise UnauthorizedError("Invalid authentication credentials")
    
    return token_data


class RoleChecker:
    """
    Dependency class for role-based access control.
    Checks if the current user has one of the required roles.
    """
    
    def __init__(self, allowed_roles: List[str]) -> None:
        """
        Initialize with list of allowed roles.
        
        Args:
            allowed_roles: List of role names that are allowed access
        """
        self.allowed_roles: List[str] = allowed_roles

    async def __call__(self, current_user: TokenData = Depends(get_current_user)) -> TokenData:
        """
        Check if current user has required role.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            TokenData if authorized
            
        Raises:
            HTTPException: If user doesn't have required role
        """
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {', '.join(self.allowed_roles)}"
            )
        return current_user


# Common role checkers for convenience
require_admin: RoleChecker = RoleChecker(["ADMIN"])
require_admin_or_manager: RoleChecker = RoleChecker(["ADMIN", "MANAGER"])
require_admin_or_staff: RoleChecker = RoleChecker(["ADMIN", "STAFF"])
require_any_role: RoleChecker = RoleChecker(["ADMIN", "MANAGER", "STAFF", "JOBBER"])
