"""
Database URL and engine-option helpers.

This module keeps driver normalization and timeout policy out of transport-
specific code so runtime DB access, Alembic, and verification scripts all use
the same connection semantics.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy.engine import make_url


DEFAULT_DATABASE_URL = "postgresql+asyncpg://fog_user:fog_password@localhost:5432/fog_compute"
DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_DATABASE_STATEMENT_TIMEOUT_SECONDS = 15


def get_sync_database_url(database_url: str) -> str:
    """Return a synchronous SQLAlchemy URL suitable for Alembic/psycopg2."""
    url = make_url(database_url)
    if url.drivername.startswith("postgresql"):
        return url.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)
    if url.drivername == "sqlite+aiosqlite":
        return url.set(drivername="sqlite").render_as_string(hide_password=False)
    return url.render_as_string(hide_password=False)


def get_async_engine_options(
    database_url: str,
    *,
    connect_timeout_seconds: int,
    statement_timeout_seconds: int,
) -> dict[str, Any]:
    """Return timeout-aware async engine kwargs for the configured DB URL."""
    drivername = make_url(database_url).drivername
    if drivername.startswith("postgresql+asyncpg"):
        return {
            "connect_args": {
                "timeout": connect_timeout_seconds,
                "command_timeout": statement_timeout_seconds,
                "server_settings": {
                    "statement_timeout": str(statement_timeout_seconds * 1000),
                },
            }
        }
    return {}


def get_sync_engine_options(
    database_url: str,
    *,
    connect_timeout_seconds: int,
    statement_timeout_seconds: int,
) -> dict[str, Any]:
    """Return timeout-aware sync engine kwargs for Alembic and verification."""
    drivername = make_url(get_sync_database_url(database_url)).drivername
    if drivername.startswith("postgresql"):
        return {
            "connect_args": {
                "connect_timeout": connect_timeout_seconds,
                "options": f"-c statement_timeout={statement_timeout_seconds * 1000}",
            }
        }
    return {}


def get_database_runtime_settings_from_env(default_database_url: str | None = None) -> dict[str, Any]:
    """
    Read DB URL and timeout settings directly from environment variables.

    Alembic and migration verification must not import the full application
    settings object because unrelated runtime validation (for example
    `SECRET_KEY`) should not block schema operations.
    """
    database_url = os.getenv("DATABASE_URL", default_database_url or DEFAULT_DATABASE_URL)
    connect_timeout_seconds = int(
        os.getenv(
            "DATABASE_CONNECT_TIMEOUT_SECONDS",
            str(DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS),
        )
    )
    statement_timeout_seconds = int(
        os.getenv(
            "DATABASE_STATEMENT_TIMEOUT_SECONDS",
            str(DEFAULT_DATABASE_STATEMENT_TIMEOUT_SECONDS),
        )
    )
    return {
        "database_url": database_url,
        "connect_timeout_seconds": connect_timeout_seconds,
        "statement_timeout_seconds": statement_timeout_seconds,
    }
