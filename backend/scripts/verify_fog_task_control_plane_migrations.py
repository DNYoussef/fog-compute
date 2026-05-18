"""
Repeatable Postgres migration verification for the fog task control plane.

Exercises:
1. Fresh database migrate from base to head.
2. Upgrade from revision 008 to head.
3. Runtime readiness after migration.
4. Control-plane lease/start/complete lifecycle after migration.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.server.database_urls import (  # noqa: E402
    DEFAULT_DATABASE_URL,
    get_sync_database_url,
    get_sync_engine_options,
)


CONNECT_TIMEOUT_SECONDS = int(os.getenv("FOG_MIGRATION_VERIFY_CONNECT_TIMEOUT_SECONDS", "5"))
COMMAND_TIMEOUT_SECONDS = int(os.getenv("FOG_MIGRATION_VERIFY_COMMAND_TIMEOUT_SECONDS", "30"))
BASE_DATABASE_URL = os.getenv(
    "FOG_MIGRATION_VERIFY_DATABASE_URL",
    os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
)
ADMIN_DATABASE_URL = os.getenv("FOG_MIGRATION_VERIFY_ADMIN_DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "fog-migration-verification-secret-key-32chars")


def _safe_db_name(prefix: str) -> str:
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[a-zA-Z0-9_]+", name):
        raise ValueError(f"Unsafe database name generated: {name}")
    return name


def _target_async_url(database_name: str) -> str:
    return make_url(BASE_DATABASE_URL).set(database=database_name).render_as_string(hide_password=False)


def _runtime_database_owner() -> str:
    owner = make_url(BASE_DATABASE_URL).username
    if not owner:
        raise ValueError(
            "FOG_MIGRATION_VERIFY_DATABASE_URL/DATABASE_URL must include a username "
            "so verification databases can be created with the runtime owner"
        )
    return owner


def _admin_sync_url() -> str:
    if ADMIN_DATABASE_URL:
        return get_sync_database_url(ADMIN_DATABASE_URL)
    sync_url = make_url(get_sync_database_url(BASE_DATABASE_URL))
    return sync_url.set(
        database=os.getenv("FOG_MIGRATION_VERIFY_ADMIN_DATABASE", "postgres")
    ).render_as_string(hide_password=False)


def _run(cmd: list[str], *, env: dict[str, str]) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def _base_env(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": database_url,
            "SECRET_KEY": SECRET_KEY,
            "APP_ENV": env.get("APP_ENV", "development"),
        }
    )
    return env


def _verify_runtime(database_url: str) -> str:
    snippet = textwrap.dedent(
        """
        import asyncio
        from backend.server.database import verify_database_readiness
        from backend.server.services.fog_task_control_plane import FogTaskControlPlaneService

        async def main():
            migration_state = await verify_database_readiness()
            if not migration_state.get("ready", False):
                raise SystemExit(f"database not ready: {migration_state}")

            service = FogTaskControlPlaneService(lease_ttl_seconds=5)
            readiness = await service.get_readiness_snapshot(force_refresh=True)
            if not readiness.get("ready", False):
                raise SystemExit(f"control plane not ready: {readiness}")

            await service.register_worker(
                "verify-worker",
                "Verify Worker",
                "desktop",
                {"cpu_cores": 4, "memory_mb": 4096},
            )
            task = await service.create_task(
                task_id="verify-task",
                task_type="compute",
                priority="NORMAL",
                payload={"job": "verify"},
            )
            grant = await service.lease_task("verify-worker", preferred_task_id=task.task_id)
            if grant is None:
                raise SystemExit("lease grant missing")
            await service.start_task(
                task.task_id,
                worker_id="verify-worker",
                attempt_id=grant.attempt.attempt_id,
                lease_id=grant.lease.lease_id,
            )
            completed, duplicate = await service.complete_task(
                task.task_id,
                worker_id="verify-worker",
                attempt_id=grant.attempt.attempt_id,
                lease_id=grant.lease.lease_id,
                success=True,
                result={"ok": True},
                error=None,
                execution_time_ms=5,
            )
            if duplicate or completed.status != "SUCCEEDED":
                raise SystemExit(f"unexpected completion result: duplicate={duplicate}, status={completed.status}")
            print("runtime-ok")

        asyncio.run(main())
        """
    )
    return _run([sys.executable, "-c", snippet], env=_base_env(database_url))


def _with_admin_connection():
    admin_url = _admin_sync_url()
    engine = create_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        **get_sync_engine_options(
            admin_url,
            connect_timeout_seconds=CONNECT_TIMEOUT_SECONDS,
            statement_timeout_seconds=COMMAND_TIMEOUT_SECONDS,
        ),
    )
    return engine


def _recreate_database(database_name: str) -> None:
    engine = _with_admin_connection()
    owner = _runtime_database_owner()
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
            conn.exec_driver_sql(f'CREATE DATABASE "{database_name}" OWNER "{owner}"')
    finally:
        engine.dispose()


def _drop_database(database_name: str) -> None:
    engine = _with_admin_connection()
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        engine.dispose()


def _verify_fresh_path(database_name: str) -> None:
    database_url = _target_async_url(database_name)
    env = _base_env(database_url)
    _run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], env=env)
    _verify_runtime(database_url)


def _verify_upgrade_path(database_name: str) -> None:
    database_url = _target_async_url(database_name)
    env = _base_env(database_url)
    _run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "008"], env=env)
    _run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], env=env)
    _verify_runtime(database_url)


def main() -> int:
    fresh_db = _safe_db_name("fog_cp_migrate_fresh")
    upgrade_db = _safe_db_name("fog_cp_migrate_upgrade")

    try:
        _recreate_database(fresh_db)
        _verify_fresh_path(fresh_db)
        print(f"fresh_path_ok database={fresh_db}")

        _recreate_database(upgrade_db)
        _verify_upgrade_path(upgrade_db)
        print(f"upgrade_path_ok database={upgrade_db}")
        return 0
    except SQLAlchemyError as exc:
        message = str(exc).lower()
        if "permission denied to create database" in message:
            print(
                "verification_failed: admin database role lacks CREATE DATABASE. "
                "Set FOG_MIGRATION_VERIFY_ADMIN_DATABASE_URL to a superuser or CREATEDB-capable role.",
                file=sys.stderr,
            )
            print(f"details: {exc}", file=sys.stderr)
            return 1
        if "password authentication failed" in message:
            print(
                "verification_failed: database authentication failed. "
                "Set DATABASE_URL and, if needed, FOG_MIGRATION_VERIFY_ADMIN_DATABASE_URL to valid credentials.",
                file=sys.stderr,
            )
            print(f"details: {exc}", file=sys.stderr)
            return 1
        raise
    finally:
        for database_name in (fresh_db, upgrade_db):
            try:
                _drop_database(database_name)
            except Exception as exc:  # pragma: no cover - cleanup-only path
                print(f"cleanup_failed database={database_name} error={exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
