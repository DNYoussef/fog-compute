"""
SQLAlchemy Database Models
Defines database schemas for all fog-compute entities
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()


class Job(Base):
    """
    Batch scheduler job
    Tracks submitted jobs through their lifecycle
    """
    __tablename__ = 'jobs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    sla_tier = Column(String(50), nullable=False)  # platinum, gold, silver, bronze
    status = Column(String(50), default='pending')  # pending, running, completed, failed
    cpu_required = Column(Float, nullable=False)
    memory_required = Column(Float, nullable=False)
    gpu_required = Column(Float, default=0.0)
    duration_estimate = Column(Float, nullable=True)
    data_size_mb = Column(Float, nullable=True)
    assigned_node = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Float, default=0.0)
    result = Column(JSON, nullable=True)
    logs = Column(Text, nullable=True)

    def to_dict(self):
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

    address = Column(String(66), primary_key=True)  # 0x + 64 hex chars
    balance = Column(Float, default=0.0)
    staked = Column(Float, default=0.0)
    rewards = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
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

    device_id = Column(String(255), primary_key=True)
    device_type = Column(String(50), nullable=False)  # android, ios, desktop
    status = Column(String(50), default='idle')  # idle, active, harvesting, offline
    battery_percent = Column(Float, default=100.0)
    is_charging = Column(Boolean, default=False)
    cpu_cores = Column(Integer, default=1)
    memory_mb = Column(Integer, default=1024)
    cpu_temp_celsius = Column(Float, nullable=True)
    tasks_completed = Column(Integer, default=0)
    compute_hours = Column(Float, default=0.0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
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

    circuit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hops = Column(JSON, nullable=False)  # List of node IDs
    bandwidth = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    health = Column(Float, default=1.0)  # 0.0 to 1.0
    created_at = Column(DateTime, default=datetime.utcnow)
    destroyed_at = Column(DateTime, nullable=True)

    def to_dict(self):
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

    proposal_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    proposer = Column(String(66), nullable=False)
    status = Column(String(50), default='active')  # active, passed, rejected, executed
    votes_for = Column(Integer, default=0)
    votes_against = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    voting_ends_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)

    def to_dict(self):
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

    stake_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address = Column(String(66), ForeignKey('token_balances.address'), nullable=False)
    amount = Column(Float, nullable=False)
    rewards_earned = Column(Float, default=0.0)
    staked_at = Column(DateTime, default=datetime.utcnow)
    unstaked_at = Column(DateTime, nullable=True)

    def to_dict(self):
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

    node_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_type = Column(String(50), default='mixnode')
    region = Column(String(50), nullable=True)
    status = Column(String(50), default='deploying')  # deploying, active, stopped, failed
    ip_address = Column(String(45), nullable=True)
    packets_processed = Column(Integer, default=0)
    uptime_seconds = Column(Integer, default=0)
    deployed_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
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
