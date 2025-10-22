"""
Authentication module for Fog Compute Backend
Provides JWT token management and password hashing
"""
from .jwt_utils import create_access_token, verify_token, get_password_hash, verify_password
from .dependencies import get_current_user, get_current_active_user, require_auth

__all__ = [
    "create_access_token",
    "verify_token",
    "get_password_hash",
    "verify_password",
    "get_current_user",
    "get_current_active_user",
    "require_auth",
]
