"""Create audit_logs table with immutability protection

Revision ID: 003
Revises: 002_advanced_bitchat
Create Date: 2025-11-25 00:00:00.000000

This migration creates the audit_logs table for security compliance.
The table is designed to be immutable (append-only) with the following features:
- Comprehensive audit trail with HTTP request/response details
- Indexed for common query patterns (timestamp, user_id, action)
- Database trigger to prevent UPDATE/DELETE operations
- JSONB metadata for flexible additional context
- Optional time-based partitioning support (commented, can be enabled)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision: str = '003'
down_revision: Union[str, Sequence[str], None] = '002_advanced_bitchat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_logs table with immutability protection."""

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('correlation_id', UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('request_method', sa.String(10), nullable=True),
        sa.Column('request_path', sa.String(500), nullable=True),
        sa.Column('response_status', sa.Integer, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create compound indexes for efficient querying
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('idx_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_correlation', 'audit_logs', ['correlation_id'])
    op.create_index('idx_audit_user_timestamp', 'audit_logs', ['user_id', 'timestamp'])
    op.create_index('idx_audit_action_timestamp', 'audit_logs', ['action', 'timestamp'])

    # Create trigger function to prevent modifications
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Prevent UPDATE operations
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'audit_logs table is immutable: UPDATE operations are not allowed';
            END IF;

            -- Prevent DELETE operations
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'audit_logs table is immutable: DELETE operations are not allowed';
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger to enforce immutability
    op.execute("""
        CREATE TRIGGER prevent_audit_modification
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    # Optional: Create partitioning by month for large-scale deployments
    # Uncomment the following to enable time-based partitioning:
    #
    # op.execute("""
    #     -- Convert to partitioned table (PostgreSQL 10+)
    #     CREATE TABLE audit_logs_partitioned (LIKE audit_logs INCLUDING ALL)
    #     PARTITION BY RANGE (timestamp);
    #
    #     -- Create initial partition for current month
    #     CREATE TABLE audit_logs_y2025m11 PARTITION OF audit_logs_partitioned
    #     FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
    #
    #     -- Insert existing data
    #     INSERT INTO audit_logs_partitioned SELECT * FROM audit_logs;
    #
    #     -- Drop old table and rename partitioned
    #     DROP TABLE audit_logs;
    #     ALTER TABLE audit_logs_partitioned RENAME TO audit_logs;
    #
    #     -- Create function to automatically create monthly partitions
    #     CREATE OR REPLACE FUNCTION create_audit_log_partition()
    #     RETURNS void AS $$
    #     DECLARE
    #         partition_name TEXT;
    #         start_date DATE;
    #         end_date DATE;
    #     BEGIN
    #         start_date := DATE_TRUNC('month', CURRENT_DATE);
    #         end_date := start_date + INTERVAL '1 month';
    #         partition_name := 'audit_logs_y' || TO_CHAR(start_date, 'YYYY') || 'm' || TO_CHAR(start_date, 'MM');
    #
    #         EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
    #                        partition_name, start_date, end_date);
    #     END;
    #     $$ LANGUAGE plpgsql;
    # """)


def downgrade() -> None:
    """Drop audit_logs table and related objects."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_modification ON audit_logs;")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

    # Drop indexes (will be automatically dropped with table, but explicit for clarity)
    op.drop_index('idx_audit_action_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_user_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_correlation', table_name='audit_logs')
    op.drop_index('idx_audit_resource', table_name='audit_logs')
    op.drop_index('idx_audit_action', table_name='audit_logs')
    op.drop_index('idx_audit_user_id', table_name='audit_logs')
    op.drop_index('idx_audit_timestamp', table_name='audit_logs')

    # Drop table
    op.drop_table('audit_logs')
