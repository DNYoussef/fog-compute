"""Add MFA fields to users table

Revision ID: 008
Revises: 007
Create Date: 2026-01-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add MFA fields to users table."""
    # Add MFA columns to users table
    op.add_column('users', sa.Column('mfa_secret', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('mfa_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('mfa_backup_codes', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove MFA fields from users table."""
    op.drop_column('users', 'mfa_enabled_at')
    op.drop_column('users', 'mfa_backup_codes')
    op.drop_column('users', 'mfa_verified')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_secret')
