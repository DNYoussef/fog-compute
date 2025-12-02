"""
Authentication Schemas
Pydantic models for auth requests and responses
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, field_serializer
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
import re


class UserCreate(BaseModel):
    """Schema for user registration"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Ensure username is alphanumeric with underscores/hyphens only"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must be alphanumeric with underscores or hyphens only')
        return v.lower()

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Ensure password has minimum complexity"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Schema for user data in responses (excludes password)"""
    id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string during validation"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    """Schema for decoded token payload"""
    username: Optional[str] = None
    user_id: Optional[str] = None
