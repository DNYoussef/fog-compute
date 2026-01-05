"""Add FOG optimization models (Node and TaskAssignment)

Revision ID: 001_fog_optimization
Revises: 8c1adce3f0c1
Create Date: 2025-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_fog_optimization'
down_revision: Union[str, None] = '8c1adce3f0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create nodes table
    op.create_table(
        'nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('node_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('node_type', sa.String(50), nullable=False, index=True),
        sa.Column('region', sa.String(100), nullable=True, index=True),
        sa.Column('status', sa.String(50), default='idle', nullable=False, index=True),

        # Hardware specs
        sa.Column('cpu_cores', sa.Integer, default=1, nullable=False),
        sa.Column('memory_mb', sa.Integer, default=1024, nullable=False),
        sa.Column('storage_gb', sa.Integer, default=10, nullable=False),
        sa.Column('gpu_available', sa.Boolean, default=False, nullable=False),

        # Performance metrics
        sa.Column('cpu_usage_percent', sa.Float, default=0.0, nullable=False),
        sa.Column('memory_usage_percent', sa.Float, default=0.0, nullable=False),
        sa.Column('network_bandwidth_mbps', sa.Float, default=0.0, nullable=False),

        # Task tracking
        sa.Column('active_tasks', sa.Integer, default=0, nullable=False),
        sa.Column('completed_tasks', sa.Integer, default=0, nullable=False),
        sa.Column('failed_tasks', sa.Integer, default=0, nullable=False),

        # Privacy features
        sa.Column('supports_onion_routing', sa.Boolean, default=False, nullable=False),
        sa.Column('circuit_participation_count', sa.Integer, default=0, nullable=False),

        # Timestamps
        sa.Column('registered_at', sa.DateTime, nullable=False),
        sa.Column('last_heartbeat', sa.DateTime, nullable=False, index=True),
    )

    # Create task_assignments table
    op.create_table(
        'task_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('node_id', sa.String(255), sa.ForeignKey('nodes.node_id'), nullable=False, index=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id'), nullable=True, index=True),

        # Task details
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('priority', sa.Integer, default=5, nullable=False),

        # Resource requirements
        sa.Column('cpu_required', sa.Float, default=1.0, nullable=False),
        sa.Column('memory_required', sa.Float, default=512.0, nullable=False),
        sa.Column('gpu_required', sa.Boolean, default=False, nullable=False),

        # Execution tracking
        sa.Column('status', sa.String(50), default='pending', nullable=False, index=True),
        sa.Column('assigned_at', sa.DateTime, nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),

        # Performance metrics
        sa.Column('execution_time_ms', sa.Float, nullable=True),
        sa.Column('retry_count', sa.Integer, default=0, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
    )

    # Create compound indexes for common queries
    op.create_index('idx_nodes_status_region', 'nodes', ['status', 'region'])
    op.create_index('idx_nodes_type_status', 'nodes', ['node_type', 'status'])
    op.create_index('idx_nodes_heartbeat', 'nodes', ['last_heartbeat'])

    op.create_index('idx_task_assignments_status_node', 'task_assignments', ['status', 'node_id'])
    op.create_index('idx_task_assignments_job', 'task_assignments', ['job_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_task_assignments_job', table_name='task_assignments')
    op.drop_index('idx_task_assignments_status_node', table_name='task_assignments')
    op.drop_index('idx_nodes_heartbeat', table_name='nodes')
    op.drop_index('idx_nodes_type_status', table_name='nodes')
    op.drop_index('idx_nodes_status_region', table_name='nodes')

    # Drop tables
    op.drop_table('task_assignments')
    op.drop_table('nodes')
