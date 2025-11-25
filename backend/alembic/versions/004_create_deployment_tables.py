"""Create deployment tables for fog-compute orchestration

Revision ID: 004_create_deployment
Revises: 003
Create Date: 2025-11-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_create_deployment'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Create deployment system tables"""

    # Create deployment_status enum
    deployment_status = postgresql.ENUM(
        'pending', 'scheduled', 'running', 'stopped', 'failed', 'deleted',
        name='deploymentstatus',
        create_type=True
    )
    deployment_status.create(op.get_bind())

    # Create replica_status enum
    replica_status = postgresql.ENUM(
        'pending', 'starting', 'running', 'stopping', 'stopped', 'failed',
        name='replicastatus',
        create_type=True
    )
    replica_status.create(op.get_bind())

    # 1. Create deployments table
    op.create_table(
        'deployments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('container_image', sa.String(500), nullable=False),
        sa.Column('status', deployment_status, nullable=False, index=True, server_default='pending'),
        sa.Column('target_replicas', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime, nullable=True, index=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create compound index for active deployments per user
    op.create_index(
        'idx_deployments_user_active',
        'deployments',
        ['user_id', 'deleted_at'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # Create unique constraint for deployment name per user (excluding deleted)
    op.create_index(
        'idx_deployments_user_name_unique',
        'deployments',
        ['user_id', 'name'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # 2. Create deployment_replicas table
    op.create_table(
        'deployment_replicas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('status', replica_status, nullable=False, index=True, server_default='pending'),
        sa.Column('container_id', sa.String(255), nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('stopped_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='SET NULL'),
    )

    # Create index for replica queries by deployment and status
    op.create_index(
        'idx_replicas_deployment_status',
        'deployment_replicas',
        ['deployment_id', 'status']
    )

    # 3. Create deployment_resources table
    op.create_table(
        'deployment_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('cpu_cores', sa.Float, nullable=False),
        sa.Column('memory_mb', sa.Integer, nullable=False),
        sa.Column('gpu_units', sa.Integer, nullable=False, server_default='0'),
        sa.Column('storage_gb', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='CASCADE'),
    )

    # 4. Create deployment_status_history table
    op.create_table(
        'deployment_status_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('old_status', sa.String(50), nullable=False),
        sa.Column('new_status', sa.String(50), nullable=False),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('changed_at', sa.DateTime, nullable=False, index=True, server_default=sa.text('now()')),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
    )

    # Create index for status history queries
    op.create_index(
        'idx_status_history_deployment_time',
        'deployment_status_history',
        ['deployment_id', 'changed_at']
    )


def downgrade():
    """Drop deployment system tables"""

    # Drop tables in reverse order (respect foreign keys)
    op.drop_table('deployment_status_history')
    op.drop_table('deployment_resources')
    op.drop_table('deployment_replicas')
    op.drop_table('deployments')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS replicastatus')
    op.execute('DROP TYPE IF EXISTS deploymentstatus')
