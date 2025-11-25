"""
API Key Schemas
Pydantic models for API key management requests and responses
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Descriptive name for the API key (e.g., 'Production Server', 'CI/CD Pipeline')"
    )
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=3650,
        description="Optional expiration in days (1-3650 days, null = no expiration)"
    )
    rate_limit: int = Field(
        1000,
        ge=1,
        le=100000,
        description="Requests per hour limit (1-100000, default: 1000)"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is not just whitespace"""
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace only')
        return v.strip()


class APIKeyResponse(BaseModel):
    """
    Schema for API key metadata in responses

    Note: Secret key is NEVER included in this schema
    """
    id: str
    name: str
    rate_limit: int
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string during validation"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class APIKeyWithSecret(APIKeyResponse):
    """
    Schema for API key creation response

    This is the ONLY time the secret key is visible.
    It includes all metadata plus the plain text secret key.
    """
    secret_key: str = Field(
        ...,
        description="Plain text API key - SAVE THIS IMMEDIATELY! It cannot be retrieved again."
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Production Server",
                "secret_key": "fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v",
                "rate_limit": 1000,
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "last_used": None,
                "expires_at": "2024-07-15T10:30:00Z"
            }
        }


class APIKeyList(BaseModel):
    """Schema for listing API keys"""
    keys: List[APIKeyResponse]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "keys": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Production Server",
                        "rate_limit": 1000,
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "last_used": "2024-01-20T15:45:00Z",
                        "expires_at": "2024-07-15T10:30:00Z"
                    },
                    {
                        "id": "987e6543-e21b-43d2-a654-426614174001",
                        "name": "CI/CD Pipeline",
                        "rate_limit": 500,
                        "is_active": True,
                        "created_at": "2024-01-10T08:00:00Z",
                        "last_used": "2024-01-21T09:30:00Z",
                        "expires_at": None
                    }
                ],
                "total": 2
            }
        }
