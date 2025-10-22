"""add_peer_and_message_models_for_bitchat

Revision ID: 8c1adce3f0c1
Revises: a174671c6fb7
Create Date: 2025-10-21 22:32:43.392406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c1adce3f0c1'
down_revision: Union[str, Sequence[str], None] = 'a174671c6fb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create peers table
    op.create_table(
        'peers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('peer_id', sa.String(length=255), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=False),
        sa.Column('is_online', sa.Boolean(), nullable=False),
        sa.Column('trust_score', sa.Float(), nullable=False),
        sa.Column('messages_sent', sa.Integer(), nullable=False),
        sa.Column('messages_received', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('peer_id')
    )
    op.create_index(op.f('ix_peers_peer_id'), 'peers', ['peer_id'], unique=True)

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('from_peer_id', sa.String(length=255), nullable=False),
        sa.Column('to_peer_id', sa.String(length=255), nullable=True),
        sa.Column('group_id', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('encryption_algorithm', sa.String(length=50), nullable=False),
        sa.Column('nonce', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('ttl', sa.Integer(), nullable=False),
        sa.Column('hop_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
        sa.ForeignKeyConstraint(['from_peer_id'], ['peers.peer_id']),
        sa.ForeignKeyConstraint(['to_peer_id'], ['peers.peer_id'])
    )
    op.create_index(op.f('ix_messages_message_id'), 'messages', ['message_id'], unique=True)
    op.create_index(op.f('ix_messages_from_peer_id'), 'messages', ['from_peer_id'], unique=False)
    op.create_index(op.f('ix_messages_to_peer_id'), 'messages', ['to_peer_id'], unique=False)
    op.create_index(op.f('ix_messages_group_id'), 'messages', ['group_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_messages_group_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_to_peer_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_from_peer_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_message_id'), table_name='messages')
    op.drop_table('messages')

    op.drop_index(op.f('ix_peers_peer_id'), table_name='peers')
    op.drop_table('peers')
