"""
Bootstrap Models
================

Pydantic models for mesh bootstrap operations.

FOG-INSTALL-005: Request/response schemas for:
- Invite generation
- Device registration
- WireGuard key exchange
- Node discovery
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from datetime import datetime
from enum import Enum
import re


class NodeRole(str, Enum):
    """Role of a node in the mesh network"""
    PRIMARY = "primary"       # Main coordination node
    SECONDARY = "secondary"   # Backup coordinator
    WORKER = "worker"         # Compute worker
    RELAY = "relay"           # Traffic relay node
    GATEWAY = "gateway"       # Edge gateway


class NodeStatus(str, Enum):
    """Current status of a mesh node"""
    PENDING = "pending"       # Awaiting registration
    ACTIVE = "active"         # Fully operational
    INACTIVE = "inactive"     # Temporarily offline
    SUSPENDED = "suspended"   # Administratively suspended


class WireGuardKeyPair(BaseModel):
    """WireGuard public/private key pair"""
    public_key: str = Field(..., description="WireGuard public key (base64)")
    private_key: str = Field(..., description="WireGuard private key (base64)")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "public_key": "aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Qga2V5YWE=",
                "private_key": "cHJpdmF0ZSBrZXkgaGVyZSBpbiBiYXNlNjQgZm9ybWF0",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


# === Invite Models ===

class InviteRequest(BaseModel):
    """Request to generate a mesh invite"""
    mesh_name: str = Field(
        default="fog-mesh",
        min_length=1,
        max_length=64,
        description="Name of the mesh network"
    )
    expires_in_minutes: int = Field(
        default=60,
        ge=5,
        le=10080,  # Max 1 week
        description="Invite expiration time in minutes"
    )
    intended_role: NodeRole = Field(
        default=NodeRole.WORKER,
        description="Intended role for the joining device"
    )
    max_uses: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Maximum number of times this invite can be used"
    )
    note: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional note about this invite"
    )
    allowed_ips: Optional[list[str]] = Field(
        default=None,
        description="Optional list of allowed IP ranges (CIDR notation)"
    )

    @field_validator('mesh_name')
    @classmethod
    def validate_mesh_name(cls, v: str) -> str:
        """Validate mesh name format"""
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_]*$', v):
            raise ValueError('Mesh name must be alphanumeric with hyphens/underscores')
        return v.lower()


class InviteResponse(BaseModel):
    """Response containing invite details and QR code"""
    invite_token: str = Field(..., description="Unique invite token")
    invite_url: str = Field(..., description="Full invite URL for joining")
    qr_code_base64: str = Field(..., description="QR code image in base64 (PNG)")
    qr_code_svg: str = Field(..., description="QR code in SVG format")
    mesh_name: str
    intended_role: NodeRole
    expires_at: datetime
    max_uses: int
    current_uses: int = 0
    bootstrap_server_url: str = Field(..., description="URL of the bootstrap server")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# === Device Registration Models ===

class DeviceCapabilities(BaseModel):
    """Hardware and software capabilities of a device"""
    cpu_cores: int = Field(default=1, ge=1, le=1024)
    ram_gb: float = Field(default=1.0, ge=0.5, le=16384)
    gpu_available: bool = False
    gpu_vram_gb: Optional[float] = Field(default=None, ge=0)
    storage_gb: float = Field(default=10.0, ge=1)
    bandwidth_mbps: float = Field(default=10.0, ge=1)
    supports_tpu: bool = False
    os_type: str = Field(default="linux", description="Operating system type")
    os_version: Optional[str] = None
    arch: str = Field(default="x86_64", description="CPU architecture")


class NetworkInfo(BaseModel):
    """Network information for a device"""
    public_ip: Optional[str] = Field(default=None, description="Public IP address")
    private_ip: Optional[str] = Field(default=None, description="Private/LAN IP address")
    listen_port: int = Field(default=51820, ge=1024, le=65535, description="WireGuard listen port")
    endpoint: Optional[str] = Field(default=None, description="Public endpoint (ip:port)")
    nat_type: Optional[str] = Field(default=None, description="NAT type if detected")


class DeviceRegistrationRequest(BaseModel):
    """Request to register a device in the mesh"""
    invite_token: str = Field(..., min_length=20, description="Valid invite token")
    device_name: str = Field(..., min_length=1, max_length=100, description="Human-readable device name")
    hostname: str = Field(..., min_length=1, max_length=255, description="Device hostname")
    public_key: str = Field(..., description="WireGuard public key")
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)
    network_info: NetworkInfo = Field(default_factory=NetworkInfo)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional device metadata")

    @field_validator('device_name')
    @classmethod
    def validate_device_name(cls, v: str) -> str:
        """Validate device name format"""
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_\s]*$', v):
            raise ValueError('Device name must be alphanumeric with hyphens/underscores/spaces')
        return v.strip()

    @field_validator('hostname')
    @classmethod
    def validate_hostname(cls, v: str) -> str:
        """Validate hostname format"""
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$', v):
            raise ValueError('Hostname must be alphanumeric, starting with letter/number')
        return v.lower()

    @field_validator('public_key')
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        """Validate WireGuard public key format (base64, 44 chars)"""
        import base64
        try:
            decoded = base64.b64decode(v)
            if len(decoded) != 32:
                raise ValueError('WireGuard public key must be 32 bytes')
        except Exception:
            raise ValueError('Invalid WireGuard public key format (must be valid base64)')
        return v


class DeviceRegistrationResponse(BaseModel):
    """Response after successful device registration"""
    device_id: str = Field(..., description="Unique device identifier in the mesh")
    mesh_token: str = Field(..., description="Authentication token for mesh operations")
    assigned_role: NodeRole
    assigned_ip: str = Field(..., description="Assigned mesh IP address (e.g., 10.0.0.x)")
    mesh_cidr: str = Field(default="10.0.0.0/24", description="Mesh network CIDR")
    primary_node_endpoint: Optional[str] = Field(default=None, description="Primary node WireGuard endpoint")
    primary_node_public_key: Optional[str] = Field(default=None, description="Primary node WireGuard public key")
    peer_endpoints: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of peer endpoints for initial connection"
    )
    dns_servers: list[str] = Field(default_factory=lambda: ["10.0.0.1"], description="Mesh DNS servers")
    heartbeat_interval_sec: int = 30
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    message: str = "Successfully registered in the mesh"


# === Key Exchange Models ===

class KeyExchangeRequest(BaseModel):
    """Request for WireGuard key exchange between nodes"""
    device_id: str = Field(..., description="Device ID of the requesting node")
    mesh_token: str = Field(..., description="Valid mesh authentication token")
    public_key: str = Field(..., description="WireGuard public key to exchange")
    target_device_id: Optional[str] = Field(
        default=None,
        description="Specific device to exchange keys with (optional)"
    )
    include_relay_nodes: bool = Field(
        default=True,
        description="Include relay nodes in key exchange"
    )

    @field_validator('public_key')
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        """Validate WireGuard public key format"""
        import base64
        try:
            decoded = base64.b64decode(v)
            if len(decoded) != 32:
                raise ValueError('WireGuard public key must be 32 bytes')
        except Exception:
            raise ValueError('Invalid WireGuard public key format')
        return v


class PeerKeyInfo(BaseModel):
    """Key information for a mesh peer"""
    device_id: str
    device_name: str
    public_key: str
    endpoint: Optional[str] = None
    allowed_ips: list[str] = Field(default_factory=list)
    persistent_keepalive: int = Field(default=25, description="Keepalive interval in seconds")
    role: NodeRole
    is_relay: bool = False


class KeyExchangeResponse(BaseModel):
    """Response containing exchanged keys and peer information"""
    success: bool = True
    your_device_id: str
    your_assigned_ip: str
    peers: list[PeerKeyInfo] = Field(default_factory=list)
    server_public_key: Optional[str] = Field(default=None, description="Bootstrap server's WireGuard public key")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# === Node Discovery Models ===

class DiscoveredNode(BaseModel):
    """Information about a discovered mesh node"""
    device_id: str
    device_name: str
    hostname: str
    role: NodeRole
    status: NodeStatus
    public_key: str
    endpoint: Optional[str] = None
    assigned_ip: str
    capabilities: DeviceCapabilities
    last_seen: datetime
    latency_ms: Optional[float] = None
    is_reachable: bool = True
    zone: str = Field(default="default")


class NodeDiscoveryResponse(BaseModel):
    """Response containing discovered mesh nodes"""
    mesh_name: str
    total_nodes: int
    active_nodes: int
    primary_node_id: Optional[str] = None
    nodes: list[DiscoveredNode] = Field(default_factory=list)
    mesh_health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# === Invite Status Models ===

class InviteStatusResponse(BaseModel):
    """Status of an invite token"""
    invite_token: str
    is_valid: bool
    mesh_name: str
    intended_role: NodeRole
    expires_at: datetime
    max_uses: int
    current_uses: int
    created_at: datetime
    is_expired: bool
    remaining_uses: int
