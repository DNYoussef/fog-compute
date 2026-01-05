"""
Create reward distribution tables

Revision ID: 005
Revises: 004
Create Date: 2025-11-25

Adds tables for tracking reward distributions, pending rewards,
batches, and audit logs to prevent reward loss during cleanup (FUNC-08).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Create reward distribution tracking tables"""

    # 1. reward_distributions table
    op.create_table(
        'reward_distributions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('reward_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('account_id', sa.String(255), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('deployment_id', UUID(as_uuid=True), sa.ForeignKey('deployments.id'), nullable=True, index=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('reward_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending', nullable=False, index=True),
        sa.Column('created_at', sa.DateTime, nullable=False, index=True),
        sa.Column('distributed_at', sa.DateTime, nullable=True),
        sa.Column('rolled_back_at', sa.DateTime, nullable=True),
        sa.Column('metadata', JSON, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('transfer_tx_id', sa.String(255), nullable=True),
        sa.Column('rollback_tx_id', sa.String(255), nullable=True),
    )

    # 2. pending_reward_queue table
    op.create_table(
        'pending_reward_queue',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('reward_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('account_id', sa.String(255), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('deployment_id', UUID(as_uuid=True), sa.ForeignKey('deployments.id'), nullable=True, index=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('reward_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='queued', nullable=False, index=True),
        sa.Column('priority', sa.String(50), default='normal', nullable=False),
        sa.Column('retry_count', sa.Float, default=0, nullable=False),
        sa.Column('max_retries', sa.Float, default=3, nullable=False),
        sa.Column('last_retry_at', sa.DateTime, nullable=True),
        sa.Column('queued_at', sa.DateTime, nullable=False, index=True),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True, index=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('metadata', JSON, nullable=True),
    )

    # 3. reward_distribution_batches table
    op.create_table(
        'reward_distribution_batches',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('batch_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('batch_type', sa.String(50), nullable=False),
        sa.Column('trigger_event', sa.String(255), nullable=True),
        sa.Column('deployment_id', UUID(as_uuid=True), sa.ForeignKey('deployments.id'), nullable=True, index=True),
        sa.Column('status', sa.String(50), default='pending', nullable=False, index=True),
        sa.Column('total_rewards', sa.Float, default=0, nullable=False),
        sa.Column('total_amount', sa.Float, default=0.0, nullable=False),
        sa.Column('successful_distributions', sa.Float, default=0, nullable=False),
        sa.Column('failed_distributions', sa.Float, default=0, nullable=False),
        sa.Column('rollback_performed', sa.Boolean, default=False, nullable=False),
        sa.Column('rollback_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, index=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('rolled_back_at', sa.DateTime, nullable=True),
        sa.Column('reward_ids', JSON, nullable=True),
        sa.Column('metadata', JSON, nullable=True),
    )

    # 4. reward_distribution_audit_log table
    op.create_table(
        'reward_distribution_audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('reward_id', sa.String(255), nullable=False, index=True),
        sa.Column('batch_id', sa.String(255), nullable=True, index=True),
        sa.Column('account_id', sa.String(255), nullable=True, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('amount', sa.Float, nullable=True),
        sa.Column('from_account', sa.String(255), nullable=True),
        sa.Column('to_account', sa.String(255), nullable=True),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('transaction_id', sa.String(255), nullable=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, index=True),
        sa.Column('event_data', JSON, nullable=True),
    )

    # Create indexes for common queries
    op.create_index(
        'idx_reward_distributions_user_deployment',
        'reward_distributions',
        ['user_id', 'deployment_id']
    )

    op.create_index(
        'idx_pending_reward_queue_status_priority',
        'pending_reward_queue',
        ['status', 'priority']
    )

    op.create_index(
        'idx_audit_log_reward_timestamp',
        'reward_distribution_audit_log',
        ['reward_id', 'timestamp']
    )


def downgrade():
    """Drop reward distribution tracking tables"""

    # Drop indexes first
    op.drop_index('idx_audit_log_reward_timestamp', table_name='reward_distribution_audit_log')
    op.drop_index('idx_pending_reward_queue_status_priority', table_name='pending_reward_queue')
    op.drop_index('idx_reward_distributions_user_deployment', table_name='reward_distributions')

    # Drop tables
    op.drop_table('reward_distribution_audit_log')
    op.drop_table('reward_distribution_batches')
    op.drop_table('pending_reward_queue')
    op.drop_table('reward_distributions')
