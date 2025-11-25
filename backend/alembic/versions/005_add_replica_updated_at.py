"""Add updated_at column to deployment_replicas

Revision ID: 005
Revises: 004
Create Date: 2025-11-25

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add updated_at column to deployment_replicas table"""
    op.add_column(
        'deployment_replicas',
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )


def downgrade() -> None:
    """Remove updated_at column from deployment_replicas table"""
    op.drop_column('deployment_replicas', 'updated_at')
