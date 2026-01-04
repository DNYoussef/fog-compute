"""
SQLAlchemy Database Models
Defines database schemas for all fog-compute entities
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

from ..constants import ONE_MB

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeMeta


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime for SQLAlchemy defaults."""
    return datetime.now(timezone.utc)


Base: "DeclarativeMeta" = declarative_base()


class Job(Base):
    """
    Batch scheduler job
    Tracks submitted jobs through their lifecycle
    """
    __tablename__ = 'jobs'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sla_tier: Mapped[str] = mapped_column(String(50), nullable=False)  # platinum, gold, silver, bronze
    status: Mapped[str] = mapped_column(String(50), default='pending')  # pending, running, completed, failed
    cpu_required: Mapped[float] = mapped_column(Float, nullable=False)
    memory_required: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_required: Mapped[float] = mapped_column(Float, default=0.0)
    duration_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_node: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'name': self.name,
            'sla_tier': self.sla_tier,
            'status': self.status,
            'cpu_required': self.cpu_required,
            'memory_required': self.memory_required,
            'gpu_required': self.gpu_required,
            'assigned_node': self.assigned_node,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
        }


class TokenBalance(Base):
    """
    Token balances for wallet addresses
    Tracks liquid and staked token amounts
    """
    __tablename__ = 'token_balances'

    address: Mapped[str] = mapped_column(String(66), primary_key=True)  # 0x + 64 hex chars
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    staked: Mapped[float] = mapped_column(Float, default=0.0)
    rewards: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'address': self.address,
            'balance': self.balance,
            'staked': self.staked,
            'rewards': self.rewards,
            'total': self.balance + self.staked,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Device(Base):
    """
    Idle compute device registration
    Tracks mobile and edge devices for harvesting
    """
    __tablename__ = 'devices'

    device_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)  # android, ios, desktop
    status: Mapped[str] = mapped_column(String(50), default='idle')  # idle, active, harvesting, offline
    battery_percent: Mapped[float] = mapped_column(Float, default=100.0)
    is_charging: Mapped[bool] = mapped_column(Boolean, default=False)
    cpu_cores: Mapped[int] = mapped_column(Integer, default=1)
    memory_mb: Mapped[int] = mapped_column(Integer, default=1024)
    cpu_temp_celsius: Mapped[float | None] = mapped_column(Float, nullable=True)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    compute_hours: Mapped[float] = mapped_column(Float, default=0.0)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.device_id,
            'type': self.device_type,
            'status': self.status,
            'battery': self.battery_percent,
            'charging': self.is_charging,
            'cpu': self.cpu_cores,
            'memory': self.memory_mb,
            'temperature': self.cpu_temp_celsius,
            'tasks_completed': self.tasks_completed,
            'compute_hours': self.compute_hours,
            'last_seen': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }


class Circuit(Base):
    """
    VPN/Onion routing circuits
    Tracks multi-hop circuits for privacy
    """
    __tablename__ = 'circuits'

    circuit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hops: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # List of node IDs
    bandwidth: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    health: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 to 1.0
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.circuit_id),
            'hops': self.hops,
            'bandwidth': self.bandwidth,
            'latency': self.latency_ms,
            'health': self.health,
            'created': self.created_at.isoformat() if self.created_at else None,
        }


class DAOProposal(Base):
    """
    DAO governance proposals
    Tracks community proposals and votes
    """
    __tablename__ = 'dao_proposals'

    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proposer: Mapped[str] = mapped_column(String(66), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='active')  # active, passed, rejected, executed
    votes_for: Mapped[int] = mapped_column(Integer, default=0)
    votes_against: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    voting_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.proposal_id),
            'title': self.title,
            'description': self.description,
            'proposer': self.proposer,
            'status': self.status,
            'votes_for': self.votes_for,
            'votes_against': self.votes_against,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Stake(Base):
    """
    Token staking records
    Tracks individual stakes for rewards
    """
    __tablename__ = 'stakes'

    stake_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address: Mapped[str] = mapped_column(String(66), ForeignKey('token_balances.address'), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    rewards_earned: Mapped[float] = mapped_column(Float, default=0.0)
    staked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    unstaked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.stake_id),
            'address': self.address,
            'amount': self.amount,
            'rewards': self.rewards_earned,
            'staked_at': self.staked_at.isoformat() if self.staked_at else None,
        }


class BetanetNode(Base):
    """
    Betanet mixnodes
    Tracks deployed privacy network nodes
    """
    __tablename__ = 'betanet_nodes'

    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_type: Mapped[str] = mapped_column(String(50), default='mixnode')
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='deploying')  # deploying, active, stopped, failed
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    packets_processed: Mapped[int] = mapped_column(Integer, default=0)
    uptime_seconds: Mapped[int] = mapped_column(Integer, default=0)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.node_id),
            'type': self.node_type,
            'region': self.region,
            'status': self.status,
            'ip': self.ip_address,
            'packets': self.packets_processed,
            'uptime': self.uptime_seconds,
            'deployed': self.deployed_at.isoformat() if self.deployed_at else None,
        }


class User(Base):
    """
    User authentication and authorization
    Tracks registered users for API access
    """
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default='free', nullable=False, index=True)  # free, pro, enterprise
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'tier': self.tier,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class APIKey(Base):
    """
    API Key for programmatic access
    Alternative authentication method for automation
    """
    __tablename__ = 'api_keys'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)  # requests per hour
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'is_active': self.is_active,
            'rate_limit': self.rate_limit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class RateLimitEntry(Base):
    """
    Rate limiting tracking
    Tracks API request counts per endpoint/user
    """
    __tablename__ = 'rate_limits'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # IP or user ID
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_request: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'identifier': self.identifier,
            'endpoint': self.endpoint,
            'request_count': self.request_count,
            'window_start': self.window_start.isoformat() if self.window_start else None,
        }


class Peer(Base):
    """
    BitChat P2P Network Peer
    Tracks registered peers in the decentralized messaging network
    """
    __tablename__ = 'peers'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    peer_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)  # Unique peer identifier
    public_key: Mapped[str] = mapped_column(Text, nullable=False)  # Peer's public key for encryption
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # 0.0 to 1.0
    messages_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'peer_id': self.peer_id,
            'public_key': self.public_key,
            'display_name': self.display_name,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_online': self.is_online,
            'trust_score': self.trust_score,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Message(Base):
    """
    BitChat Encrypted Message
    Tracks messages exchanged in the P2P network with encryption metadata
    """
    __tablename__ = 'messages'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)  # Unique message ID
    from_peer_id: Mapped[str] = mapped_column(String(255), ForeignKey('peers.peer_id'), nullable=False, index=True)
    to_peer_id: Mapped[str | None] = mapped_column(String(255), ForeignKey('peers.peer_id'), nullable=True, index=True)  # Null for group messages
    group_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # For group chats
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted message content
    encryption_algorithm: Mapped[str] = mapped_column(String(50), default='AES-256-GCM', nullable=False)
    nonce: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Encryption nonce/IV
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)  # pending, sent, delivered, read, failed
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ttl: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)  # Time to live in seconds
    hop_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # For onion routing

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'message_id': self.message_id,
            'from_peer_id': self.from_peer_id,
            'to_peer_id': self.to_peer_id,
            'group_id': self.group_id,
            'content': self.content,
            'encryption_algorithm': self.encryption_algorithm,
            'nonce': self.nonce,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'ttl': self.ttl,
            'hop_count': self.hop_count,
        }


class Node(Base):
    """
    FOG Network Node
    Tracks fog coordinator nodes with performance metrics
    """
    __tablename__ = 'nodes'
    __table_args__ = (
        # Compound index for common queries
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # edge_device, relay_node, mixnode, compute_node, gateway
    region: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='idle', nullable=False, index=True)  # idle, active, busy, offline, maintenance

    # Hardware specs
    cpu_cores: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    storage_gb: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    gpu_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Performance metrics
    cpu_usage_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_usage_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    network_bandwidth_mbps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Task tracking
    active_tasks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_tasks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_tasks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Privacy features
    supports_onion_routing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    circuit_participation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'node_id': self.node_id,
            'node_type': self.node_type,
            'region': self.region,
            'status': self.status,
            'cpu_cores': self.cpu_cores,
            'memory_mb': self.memory_mb,
            'storage_gb': self.storage_gb,
            'gpu_available': self.gpu_available,
            'cpu_usage': self.cpu_usage_percent,
            'memory_usage': self.memory_usage_percent,
            'bandwidth': self.network_bandwidth_mbps,
            'active_tasks': self.active_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'supports_onion': self.supports_onion_routing,
            'circuits': self.circuit_participation_count,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }


class TaskAssignment(Base):
    """
    Task Assignment Tracking
    Links tasks to nodes with execution metadata
    """
    __tablename__ = 'task_assignments'
    __table_args__ = (
        # Compound indexes for efficient querying
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(255), ForeignKey('nodes.node_id'), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('jobs.id'), nullable=True, index=True)

    # Task details
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Resource requirements
    cpu_required: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    memory_required: Mapped[float] = mapped_column(Float, default=512.0, nullable=False)
    gpu_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Execution tracking
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False, index=True)  # pending, assigned, running, completed, failed
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Performance metrics
    execution_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'task_id': self.task_id,
            'node_id': self.node_id,
            'job_id': str(self.job_id) if self.job_id else None,
            'task_type': self.task_type,
            'priority': self.priority,
            'cpu_required': self.cpu_required,
            'memory_required': self.memory_required,
            'gpu_required': self.gpu_required,
            'status': self.status,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time_ms': self.execution_time_ms,
            'retry_count': self.retry_count,
        }


class GroupChat(Base):
    """
    Group Chat for BitChat
    Tracks group conversations with membership
    """
    __tablename__ = 'group_chats'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), ForeignKey('peers.peer_id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Gossip protocol metadata
    vector_clock: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, nullable=False)  # Vector clock for message ordering
    last_sync: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'group_id': self.group_id,
            'name': self.name,
            'description': self.description,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'member_count': self.member_count,
            'message_count': self.message_count,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
        }


class GroupMembership(Base):
    """
    Group Membership for BitChat
    Tracks peer membership in groups
    """
    __tablename__ = 'group_memberships'
    __table_args__ = (
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[str] = mapped_column(String(255), ForeignKey('group_chats.group_id'), nullable=False, index=True)
    peer_id: Mapped[str] = mapped_column(String(255), ForeignKey('peers.peer_id'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default='member', nullable=False)  # admin, moderator, member
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'group_id': self.group_id,
            'peer_id': self.peer_id,
            'role': self.role,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'left_at': self.left_at.isoformat() if self.left_at else None,
            'is_active': self.is_active,
            'messages_sent': self.messages_sent,
        }


class FileTransfer(Base):
    """
    File Transfer for BitChat
    Tracks file uploads/downloads with chunking
    """
    __tablename__ = 'file_transfers'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # Size in bytes
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Chunking metadata
    chunk_size: Mapped[int] = mapped_column(Integer, default=ONE_MB, nullable=False)  # 1MB chunks
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ownership and encryption
    uploaded_by: Mapped[str] = mapped_column(String(255), ForeignKey('peers.peer_id'), nullable=False, index=True)
    encryption_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Hash of encryption key

    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False, index=True)  # pending, uploading, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Multi-source download tracking
    download_sources: Mapped[list[str]] = mapped_column(JSON, default=[], nullable=False)  # List of peer IDs with complete file

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'file_id': self.file_id,
            'filename': self.filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'chunk_size': self.chunk_size,
            'total_chunks': self.total_chunks,
            'uploaded_chunks': self.uploaded_chunks,
            'uploaded_by': self.uploaded_by,
            'status': self.status,
            'progress': (self.uploaded_chunks / self.total_chunks * 100) if self.total_chunks > 0 else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'download_sources': self.download_sources,
        }


class FileChunk(Base):
    """
    File Chunk for BitChat
    Tracks individual file chunks for resume capability
    """
    __tablename__ = 'file_chunks'
    __table_args__ = (
        {'extend_existing': True}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[str] = mapped_column(String(255), ForeignKey('file_transfers.file_id'), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hash
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Path to stored chunk

    # Multi-source tracking
    available_from: Mapped[list[str]] = mapped_column(JSON, default=[], nullable=False)  # List of peer IDs with this chunk

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': str(self.id),
            'file_id': self.file_id,
            'chunk_index': self.chunk_index,
            'chunk_hash': self.chunk_hash,
            'chunk_size': self.chunk_size,
            'uploaded': self.uploaded,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'available_from': self.available_from,
        }
