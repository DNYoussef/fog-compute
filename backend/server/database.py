"""
Database connection, session management, and migration-state verification.

Runtime startup must verify connectivity and Alembic state. It must not create
or evolve schema implicitly.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
import logging
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .database_urls import get_async_engine_options
from .models.database import Base
from .models import control_plane as _control_plane_models  # noqa: F401

logger = logging.getLogger(__name__)
ALEMBIC_VERSION_TABLE = "alembic_version"


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    **get_async_engine_options(
        settings.DATABASE_URL,
        connect_timeout_seconds=settings.DATABASE_CONNECT_TIMEOUT_SECONDS,
        statement_timeout_seconds=settings.DATABASE_STATEMENT_TIMEOUT_SECONDS,
    ),
)


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@lru_cache(maxsize=1)
def get_alembic_script_directory() -> ScriptDirectory:
    """Return the Alembic script directory for topology-aware revision checks."""
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return ScriptDirectory.from_config(config)


@lru_cache(maxsize=1)
def get_alembic_head_revisions() -> tuple[str, ...]:
    """Return the Alembic head revisions expected by this codebase."""
    return tuple(sorted(get_alembic_script_directory().get_heads()))


def _is_revision_at_or_behind_head(script: ScriptDirectory, revision: str, expected_heads: list[str]) -> bool:
    """Return True when a revision is a head or an ancestor of a current head."""
    if revision in expected_heads:
        return True

    try:
        script.get_revision(revision)
    except Exception:
        return False

    for head in expected_heads:
        try:
            list(script.iterate_revisions(head, revision))
        except Exception:
            continue
        return True
    return False


def _collect_database_migration_state(sync_connection) -> dict[str, Any]:
    inspector = inspect(sync_connection)
    tables = set(inspector.get_table_names())
    expected_heads = list(get_alembic_head_revisions())
    script = get_alembic_script_directory()
    version_table_present = ALEMBIC_VERSION_TABLE in tables

    report: dict[str, Any] = {
        "ready": True,
        "state": "at_head",
        "expected_head_revisions": expected_heads,
        "current_revisions": [],
        "version_table_present": version_table_present,
    }

    if not version_table_present:
        report["ready"] = False
        report["state"] = "missing_version_table"
        return report

    rows = sync_connection.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).fetchall()
    current_revisions = [row[0] for row in rows if row[0]]
    report["current_revisions"] = current_revisions

    if not current_revisions:
        report["ready"] = False
        report["state"] = "missing_version_row"
        return report

    current_set = set(current_revisions)
    if current_set != set(expected_heads):
        report["ready"] = False
        if all(_is_revision_at_or_behind_head(script, revision, expected_heads) for revision in current_revisions):
            report["state"] = "behind_head"
        else:
            report["state"] = "unexpected_revision_state"
    return report


async def get_database_migration_state() -> dict[str, Any]:
    """Return the Alembic migration state for the configured runtime database."""
    async with engine.connect() as conn:
        return await conn.run_sync(_collect_database_migration_state)


async def verify_database_readiness() -> dict[str, Any]:
    """
    Verify DB connectivity and Alembic migration state.

    This is the only startup DB path the app should use. Operators must run
    Alembic ahead of time; startup will not mutate schema.
    """
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return await get_database_migration_state()


async def bootstrap_dev_schema() -> None:
    """
    Explicit development-only metadata bootstrap.

    This helper is never used by application startup. It exists only for local
    experimentation when developers intentionally opt in.
    """
    if settings.APP_ENV == "production":
        raise RuntimeError("Refusing dev DB bootstrap in production; run Alembic migrations instead")
    if not settings.ENABLE_DEV_DB_BOOTSTRAP:
        raise RuntimeError(
            "Dev DB bootstrap is disabled. Set ENABLE_DEV_DB_BOOTSTRAP=true in development only."
        )

    async with engine.begin() as conn:
        logger.warning("Bootstrapping database schema via metadata.create_all in %s", settings.APP_ENV)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        await conn.execute(text("DELETE FROM alembic_version"))
        for revision in get_alembic_head_revisions():
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": revision},
            )


async def close_db() -> None:
    """Close database connections on shutdown."""
    await engine.dispose()
    logger.info("Database connections closed")


async def get_db() -> AsyncSession:
    """FastAPI dependency for obtaining an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    """Context manager for one explicit async DB session scope."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
