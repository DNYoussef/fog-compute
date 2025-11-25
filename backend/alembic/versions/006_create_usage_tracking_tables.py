"""create usage tracking tables

Revision ID: 006_usage_tracking
Revises: 005_add_replica_updated_at
Create Date: 2025-11-25

Creates tables for daily usage tracking and tier-based limits:
- daily_usage: Tracks per-user daily consumption
- usage_limits: Defines limits per tier (free, pro, enterprise)
- Adds tier column to users table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """Create usage tracking tables"""

    # Add tier column to users table
    op.add_column('users', sa.Column('tier', sa.String(50), nullable=False, server_default='free'))
    op.create_index('ix_users_tier', 'users', ['tier'])

    # Create usage_limits table
    op.create_table(
        'usage_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tier', sa.String(50), nullable=False, unique=True),
        sa.Column('max_deployments_per_day', sa.Integer, nullable=True),
        sa.Column('max_api_calls_per_day', sa.Integer, nullable=True),
        sa.Column('max_compute_hours_per_day', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_storage_gb', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()'))
    )
    op.create_index('ix_usage_limits_tier', 'usage_limits', ['tier'])

    # Create daily_usage table
    op.create_table(
        'daily_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('deployments_created', sa.Integer, nullable=False, server_default='0'),
        sa.Column('api_calls', sa.Integer, nullable=False, server_default='0'),
        sa.Column('compute_hours', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('storage_gb_hours', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_daily_usage_user_id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_user_date')
    )
    op.create_index('ix_daily_usage_user_id', 'daily_usage', ['user_id'])
    op.create_index('ix_daily_usage_date', 'daily_usage', ['date'])

    # Insert default tier limits
    op.execute("""
        INSERT INTO usage_limits (id, tier, max_deployments_per_day, max_api_calls_per_day, max_compute_hours_per_day, max_storage_gb)
        VALUES
            (gen_random_uuid(), 'free', 10, 5000, 10.0, 5),
            (gen_random_uuid(), 'pro', 50, 50000, 100.0, 50),
            (gen_random_uuid(), 'enterprise', NULL, NULL, NULL, NULL)
    """)


def downgrade():
    """Drop usage tracking tables"""
    op.drop_table('daily_usage')
    op.drop_table('usage_limits')
    op.drop_index('ix_users_tier', 'users')
    op.drop_column('users', 'tier')
