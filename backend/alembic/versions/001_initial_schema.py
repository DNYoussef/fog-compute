"""Initial schema - jobs, tokens, devices, circuits, proposals, stakes, nodes

Revision ID: 001
Revises: 
Create Date: 2025-10-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Jobs table
    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('sla_tier', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('cpu_required', sa.Float(), nullable=False),
        sa.Column('memory_required', sa.Float(), nullable=False),
        sa.Column('gpu_required', sa.Float(), nullable=True),
        sa.Column('duration_estimate', sa.Float(), nullable=True),
        sa.Column('data_size_mb', sa.Float(), nullable=True),
        sa.Column('assigned_node', sa.String(length=255), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('logs', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Token balances table
    op.create_table('token_balances',
        sa.Column('address', sa.String(length=66), nullable=False),
        sa.Column('balance', sa.Float(), nullable=True),
        sa.Column('staked', sa.Float(), nullable=True),
        sa.Column('rewards', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('address')
    )

    # Devices table
    op.create_table('devices',
        sa.Column('device_id', sa.String(length=255), nullable=False),
        sa.Column('device_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('battery_percent', sa.Float(), nullable=True),
        sa.Column('is_charging', sa.Boolean(), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('memory_mb', sa.Integer(), nullable=True),
        sa.Column('cpu_temp_celsius', sa.Float(), nullable=True),
        sa.Column('tasks_completed', sa.Integer(), nullable=True),
        sa.Column('compute_hours', sa.Float(), nullable=True),
        sa.Column('registered_at', sa.DateTime(), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('device_id')
    )

    # Circuits table
    op.create_table('circuits',
        sa.Column('circuit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hops', sa.JSON(), nullable=False),
        sa.Column('bandwidth', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('health', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('destroyed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('circuit_id')
    )

    # DAO proposals table
    op.create_table('dao_proposals',
        sa.Column('proposal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('proposer', sa.String(length=66), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('votes_for', sa.Integer(), nullable=True),
        sa.Column('votes_against', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('voting_ends_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('proposal_id')
    )

    # Stakes table
    op.create_table('stakes',
        sa.Column('stake_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('address', sa.String(length=66), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('rewards_earned', sa.Float(), nullable=True),
        sa.Column('staked_at', sa.DateTime(), nullable=True),
        sa.Column('unstaked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['address'], ['token_balances.address'], ),
        sa.PrimaryKeyConstraint('stake_id')
    )

    # Betanet nodes table
    op.create_table('betanet_nodes',
        sa.Column('node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=True),
        sa.Column('region', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('packets_processed', sa.Integer(), nullable=True),
        sa.Column('uptime_seconds', sa.Integer(), nullable=True),
        sa.Column('deployed_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('node_id')
    )


def downgrade():
    op.drop_table('betanet_nodes')
    op.drop_table('stakes')
    op.drop_table('dao_proposals')
    op.drop_table('circuits')
    op.drop_table('devices')
    op.drop_table('token_balances')
    op.drop_table('jobs')
