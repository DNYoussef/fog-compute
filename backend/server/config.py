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

        CRITICAL: In CI environment, validates that DATABASE_URL env var exists.
        FIXED: Previous version compared values causing false positive when GitHub
        Actions provided URL that matched default pattern after normalization.
        """
        import os

        # CI Validation: Check if DATABASE_URL environment variable EXISTS
        # Don't compare values - GitHub Actions URL may legitimately match default pattern
        if os.getenv('CI') == 'true':
            raw_env_url = os.getenv('DATABASE_URL')
            if not raw_env_url:
                raise ValueError(
                    "❌ DATABASE_URL environment variable not set in CI. "
                    "Expected value from GitHub Actions $GITHUB_ENV export. "
                    "Check playwright.config.ts webServer env configuration."
                )
            # If we got here, DATABASE_URL exists and was inherited correctly

        # Normalize URL format (postgres:// → postgresql+asyncpg://)
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
    # CRITICAL: SECRET_KEY must be set via environment variable in production
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate SECRET_KEY is set and secure in production."""
        if os.getenv('CI') == 'true' or os.getenv('TESTING') == 'true':
            # Allow empty/default in CI/testing
            return v or "test-secret-key-for-ci-only"

        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be set via environment variable and be at least 32 characters. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    # Performance
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 60  # seconds

    # Redis
    # Default uses localhost for development
    # Production should set REDIS_URL environment variable
    # Format: redis://[:password]@host:port/db
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 10

    @field_validator('REDIS_URL')
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """
        Validate REDIS_URL format and warn if using default in production.

        Accepts formats:
        - redis://localhost:6379/0 (dev, no password)
        - redis://:password@localhost:6379/0 (prod with password)
        - redis://user:password@localhost:6379/0 (full auth)
        """
        if not v.startswith('redis://'):
            raise ValueError(
                "REDIS_URL must start with redis:// scheme. "
                f"Got: {v}"
            )

        # Warn if using localhost without password in production-like environment
        if 'localhost' in v and ':@' not in v and ':*****@' not in v:
            if os.getenv('CI') != 'true' and os.getenv('TESTING') != 'true':
                import warnings
                warnings.warn(
                    "Using Redis without password. Set REDIS_URL with password for production.",
                    UserWarning
                )

        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
