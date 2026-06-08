"""Add fog task control-plane schema guarantees.

Revision ID: 009
Revises: 008
Create Date: 2026-03-11

"""
from __future__ import annotations

from pathlib import Path
import sys

from alembic import op
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.models.control_plane import (
    ControlPlaneTask,
    ControlPlaneTaskAttempt,
    ControlPlaneTaskLease,
    ControlPlaneWorker,
    PipelineRecord,
)


# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


CONTROL_PLANE_TABLES = [
    ControlPlaneWorker.__table__,
    ControlPlaneTask.__table__,
    ControlPlaneTaskAttempt.__table__,
    ControlPlaneTaskLease.__table__,
    PipelineRecord.__table__,
]

CONTROL_PLANE_INDEXES = {
    table.name: {index.name: index for index in table.indexes}
    for table in CONTROL_PLANE_TABLES
}


def _get_index_sql(bind, table_name: str, index_name: str) -> str:
    dialect = bind.dialect.name
    if dialect == "postgresql":
        row = bind.execute(
            sa.text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = :table_name
                  AND indexname = :index_name
                """
            ),
            {"table_name": table_name, "index_name": index_name},
        ).mappings().first()
        return row["indexdef"] if row else ""
    if dialect == "sqlite":
        row = bind.execute(
            sa.text(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name = :table_name
                  AND name = :index_name
                """
            ),
            {"table_name": table_name, "index_name": index_name},
        ).mappings().first()
        return row["sql"] if row and row["sql"] else ""
    return ""


def _ensure_table(bind, table: sa.Table) -> None:
    table.create(bind, checkfirst=True)


def _ensure_index(bind, table_name: str, index_name: str) -> None:
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name in existing_indexes:
        return
    CONTROL_PLANE_INDEXES[table_name][index_name].create(bind)


def _ensure_active_lease_index(bind) -> None:
    table_name = ControlPlaneTaskLease.__table__.name
    index_name = "ix_cp_leases_active_task"
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name in existing_indexes and "ACTIVE" in (_get_index_sql(bind, table_name, index_name) or ""):
        return
    if index_name in existing_indexes:
        op.drop_index(index_name, table_name=table_name)
    CONTROL_PLANE_INDEXES[table_name][index_name].create(bind)


def upgrade() -> None:
    """Create the durable fog task control-plane schema and required indexes."""
    bind = op.get_bind()

    for table in CONTROL_PLANE_TABLES:
        _ensure_table(bind, table)

    required_indexes = (
        ("control_plane_workers", "ix_cp_workers_status"),
        ("control_plane_workers", "ix_cp_workers_owner"),
        ("control_plane_workers", "ix_cp_workers_last_heartbeat"),
        ("control_plane_tasks", "ix_cp_tasks_status"),
        ("control_plane_tasks", "ix_cp_tasks_worker"),
        ("control_plane_tasks", "ix_cp_tasks_worker_status"),
        ("control_plane_tasks", "ix_cp_tasks_pipeline"),
        ("control_plane_tasks", "ix_cp_tasks_stage"),
        ("control_plane_tasks", "ix_cp_tasks_idempotency"),
        ("control_plane_tasks", "ix_cp_tasks_created_at"),
        ("control_plane_task_attempts", "ix_cp_attempts_task"),
        ("control_plane_task_attempts", "ix_cp_attempts_worker"),
        ("control_plane_task_attempts", "ix_cp_attempts_status"),
        ("control_plane_task_attempts", "ix_cp_attempts_lease"),
        ("control_plane_task_attempts", "ix_cp_attempts_task_number"),
        ("control_plane_task_leases", "ix_cp_leases_task"),
        ("control_plane_task_leases", "ix_cp_leases_worker"),
        ("control_plane_task_leases", "ix_cp_leases_status"),
        ("control_plane_task_leases", "ix_cp_leases_expires_at"),
        ("control_plane_task_leases", "ix_cp_leases_status_expires_at"),
        ("control_plane_task_leases", "ix_cp_leases_attempt"),
        ("pipeline_records", "ix_pipeline_records_status"),
        ("pipeline_records", "ix_pipeline_records_updated_at"),
    )

    for table_name, index_name in required_indexes:
        _ensure_index(bind, table_name, index_name)

    _ensure_active_lease_index(bind)


def downgrade() -> None:
    """Remove the fog task control-plane schema."""
    bind = op.get_bind()
    for table in reversed(CONTROL_PLANE_TABLES):
        table.drop(bind, checkfirst=True)
