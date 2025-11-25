"""Add BitChat advanced features: groups and file transfer

Revision ID: 002_advanced_bitchat
Revises: 001_fog_optimization
Create Date: 2025-10-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_advanced_bitchat'
down_revision = '001_fog_optimization'
branch_labels = None
depends_on = None


def upgrade():
    # Create group_chats table
    op.create_table(
        'group_chats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('group_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_by', sa.String(255), sa.ForeignKey('peers.peer_id'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('member_count', sa.Integer, default=1, nullable=False),
        sa.Column('message_count', sa.Integer, default=0, nullable=False),
        sa.Column('vector_clock', postgresql.JSON, server_default='{}', nullable=False),
        sa.Column('last_sync', sa.DateTime, server_default=sa.text('now()'), nullable=False)
    )

    # Create group_memberships table
    op.create_table(
        'group_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('group_id', sa.String(255), sa.ForeignKey('group_chats.group_id'), nullable=False, index=True),
        sa.Column('peer_id', sa.String(255), sa.ForeignKey('peers.peer_id'), nullable=False, index=True),
        sa.Column('role', sa.String(50), default='member', nullable=False),
        sa.Column('joined_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('left_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('messages_sent', sa.Integer, default=0, nullable=False)
    )

    # Create file_transfers table
    op.create_table(
        'file_transfers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('file_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('chunk_size', sa.Integer, default=1048576, nullable=False),
        sa.Column('total_chunks', sa.Integer, nullable=False),
        sa.Column('uploaded_chunks', sa.Integer, default=0, nullable=False),
        sa.Column('uploaded_by', sa.String(255), sa.ForeignKey('peers.peer_id'), nullable=False, index=True),
        sa.Column('encryption_key_hash', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='pending', nullable=False, index=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('download_sources', postgresql.JSON, server_default='[]', nullable=False)
    )

    # Create file_chunks table
    op.create_table(
        'file_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('file_id', sa.String(255), sa.ForeignKey('file_transfers.file_id'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('chunk_hash', sa.String(64), nullable=False),
        sa.Column('chunk_size', sa.Integer, nullable=False),
        sa.Column('uploaded', sa.Boolean, default=False, nullable=False),
        sa.Column('uploaded_at', sa.DateTime, nullable=True),
        sa.Column('stored_path', sa.String(500), nullable=True),
        sa.Column('available_from', postgresql.JSON, server_default='[]', nullable=False)
    )

    # Create indexes for performance
    op.create_index('idx_group_memberships_group_peer', 'group_memberships', ['group_id', 'peer_id'])
    op.create_index('idx_file_chunks_file_index', 'file_chunks', ['file_id', 'chunk_index'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('file_chunks')
    op.drop_table('file_transfers')
    op.drop_table('group_memberships')
    op.drop_table('group_chats')
