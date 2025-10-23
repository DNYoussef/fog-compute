"""
Backend API Server Configuration
Centralized configuration for all services and connections
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TITLE: str = "Fog Compute Backend API"
    API_VERSION: str = "1.0.0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    # Default uses standard postgres credentials and test database for easier local development
    # Production should set DATABASE_URL environment variable
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fog_compute_test"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @field_validator('DATABASE_URL')
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """
        Normalize DATABASE_URL to use asyncpg driver for async SQLAlchemy.
        CI/GitHub Actions provides postgresql:// or postgres:// which defaults to psycopg2 (sync).
        We need postgresql+asyncpg:// for async support.
        """
        if v.startswith('postgresql://') and '+asyncpg' not in v:
            return v.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif v.startswith('postgres://'):
            return v.replace('postgres://', 'postgresql+asyncpg://', 1)
        return v

    # Betanet (Rust service)
    BETANET_URL: str = "http://localhost:9000"
    BETANET_TIMEOUT: int = 5

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MESSAGE_QUEUE_SIZE: int = 100

    # Service Paths (for importing Python modules)
    SRC_PATH: str = os.path.join(os.path.dirname(__file__), "../../src")

    # Monitoring
    METRICS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Performance
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 60  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
