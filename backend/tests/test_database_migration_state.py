import pytest
from sqlalchemy import text

import backend.server.database as database_module
from backend.server.database import (
    bootstrap_dev_schema,
    engine,
    get_alembic_head_revisions,
    get_database_migration_state,
    verify_database_readiness,
)
from backend.server.database_urls import (
    DEFAULT_DATABASE_URL,
    get_database_runtime_settings_from_env,
    get_sync_database_url,
)
from backend.server.models.control_plane import (
    ControlPlaneTask,
    ControlPlaneTaskAttempt,
    ControlPlaneTaskLease,
    ControlPlaneWorker,
    PipelineRecord,
)
from backend.server.models.database import Base
from backend.server.services.fog_task_control_plane import (
    ControlPlaneSchemaError,
    FogTaskControlPlaneService,
)


CONTROL_PLANE_TABLES = [
    ControlPlaneWorker.__table__,
    ControlPlaneTask.__table__,
    ControlPlaneTaskAttempt.__table__,
    ControlPlaneTaskLease.__table__,
    PipelineRecord.__table__,
]


async def _prepare_tables(*, stamped_revision: str | None) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=CONTROL_PLANE_TABLES))
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=CONTROL_PLANE_TABLES))
        if stamped_revision is not None:
            await conn.execute(
                text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            )
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": stamped_revision},
            )


@pytest.mark.asyncio
async def test_tables_without_alembic_version_are_not_ready():
    await _prepare_tables(stamped_revision=None)

    migration_state = await get_database_migration_state()
    assert migration_state["ready"] is False
    assert migration_state["state"] == "missing_version_table"

    readiness = await verify_database_readiness()
    assert readiness["ready"] is False
    assert readiness["state"] == "missing_version_table"

    control_plane = FogTaskControlPlaneService()
    snapshot = await control_plane.get_readiness_snapshot(force_refresh=True)
    assert snapshot["ready"] is False
    assert snapshot["failure_mode"] == "migration_state_missing"

    with pytest.raises(ControlPlaneSchemaError):
        await control_plane.create_task(
            task_id="task-missing-version",
            task_type="compute",
            priority="NORMAL",
            payload={"op": "blocked"},
        )


@pytest.mark.asyncio
async def test_revision_behind_head_is_not_ready():
    await _prepare_tables(stamped_revision="008")

    migration_state = await get_database_migration_state()
    assert migration_state["ready"] is False
    assert migration_state["state"] == "behind_head"
    assert migration_state["current_revisions"] == ["008"]
    assert migration_state["expected_head_revisions"] == list(get_alembic_head_revisions())

    control_plane = FogTaskControlPlaneService()
    snapshot = await control_plane.get_readiness_snapshot(force_refresh=True)
    assert snapshot["ready"] is False
    assert snapshot["failure_mode"] == "migration_state_behind_head"


@pytest.mark.asyncio
async def test_dev_bootstrap_path_is_blocked_in_production(monkeypatch):
    monkeypatch.setattr(database_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(database_module.settings, "ENABLE_DEV_DB_BOOTSTRAP", True)

    with pytest.raises(RuntimeError, match="Refusing dev DB bootstrap in production"):
        await bootstrap_dev_schema()


def test_migration_runtime_settings_are_env_only(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_CONNECT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DATABASE_STATEMENT_TIMEOUT_SECONDS", raising=False)

    settings = get_database_runtime_settings_from_env()

    assert settings["database_url"] == DEFAULT_DATABASE_URL
    assert settings["connect_timeout_seconds"] == 5
    assert settings["statement_timeout_seconds"] == 15


def test_sync_database_url_preserves_password():
    sync_url = get_sync_database_url("postgresql+asyncpg://fog_user:fog_password@localhost:5432/fog_compute")
    assert sync_url == "postgresql+psycopg2://fog_user:fog_password@localhost:5432/fog_compute"
