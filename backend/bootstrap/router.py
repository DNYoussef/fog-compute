"""
Bootstrap Server Router
=======================

FOG-INSTALL-005: FastAPI router for mesh bootstrap operations.

Endpoints:
- POST /api/v1/bootstrap/invite         - Generate QR code/invite link for mesh join
- GET  /api/v1/bootstrap/invite/{token} - Get invite status
- POST /api/v1/bootstrap/register       - Device registration with profile
- POST /api/v1/bootstrap/exchange-keys  - WireGuard key exchange
- GET  /api/v1/bootstrap/discover       - Return list of known nodes
- GET  /api/v1/bootstrap/health         - Health check
"""
from __future__ import annotations

import secrets
import logging
import ipaddress
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Depends, Query, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import (
    InviteRequest,
    InviteResponse,
    InviteStatusResponse,
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    KeyExchangeRequest,
    KeyExchangeResponse,
    NodeDiscoveryResponse,
    DiscoveredNode,
    PeerKeyInfo,
    NodeRole,
    NodeStatus,
    DeviceCapabilities,
)
from .wireguard import get_wireguard_generator, WireGuardKeyGenerator
from .qr import get_qr_generator, configure_qr_generator, QRCodeGenerator

# Import from main server if available, otherwise use standalone storage
try:
    from ..server.services.mesh_persistence import get_mesh_persistence, MeshPersistenceService
    from ..server.schemas.device_mesh import DeviceProfile, DeviceRole as MeshDeviceRole
    HAS_MESH_PERSISTENCE = True
except ImportError:
    HAS_MESH_PERSISTENCE = False
    MeshPersistenceService = None

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/api/v1/bootstrap",
    tags=["bootstrap"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    }
)

# Security
security = HTTPBearer(auto_error=False)


# === In-Memory Storage (for standalone mode) ===

@dataclass
class InviteRecord:
    """In-memory storage for invite tokens"""
    token: str
    token_hash: str
    mesh_name: str
    intended_role: NodeRole
    expires_at: datetime
    max_uses: int
    current_uses: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    allowed_ips: Optional[list[str]] = None
    note: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if invite is still valid"""
        now = datetime.now(timezone.utc)
        return (
            self.current_uses < self.max_uses and
            self.expires_at > now
        )


@dataclass
class RegisteredDevice:
    """In-memory storage for registered devices"""
    device_id: str
    device_name: str
    hostname: str
    public_key: str
    assigned_ip: str
    assigned_role: NodeRole
    mesh_token: str
    mesh_token_hash: str
    capabilities: DeviceCapabilities
    endpoint: Optional[str] = None
    status: NodeStatus = NodeStatus.ACTIVE
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BootstrapStore:
    """
    In-memory storage for bootstrap operations.

    In production, this should be backed by MeshPersistenceService.
    """

    def __init__(self):
        self.invites: dict[str, InviteRecord] = {}
        self.devices: dict[str, RegisteredDevice] = {}
        self.mesh_tokens: dict[str, str] = {}  # token_hash -> device_id
        self.ip_allocations: set[str] = set()
        self.base_ip = ipaddress.IPv4Address("10.0.0.1")
        self.next_ip_offset = 2  # Start from 10.0.0.2 (10.0.0.1 is server)
        self.mesh_cidr = "10.0.0.0/24"
        self.mesh_name = "fog-mesh"
        self.primary_device_id: Optional[str] = None

    def allocate_ip(self) -> str:
        """Allocate the next available mesh IP"""
        while True:
            ip = str(self.base_ip + self.next_ip_offset)
            self.next_ip_offset += 1
            if ip not in self.ip_allocations:
                self.ip_allocations.add(ip)
                return ip
            # Safety check to prevent infinite loop
            if self.next_ip_offset > 254:
                raise RuntimeError("IP address pool exhausted")

    def store_invite(self, record: InviteRecord) -> None:
        """Store an invite record"""
        self.invites[record.token_hash] = record

    def get_invite(self, token: str) -> Optional[InviteRecord]:
        """Get invite by plaintext token"""
        token_hash = self._hash_token(token)
        return self.invites.get(token_hash)

    def use_invite(self, token: str) -> bool:
        """Mark an invite as used"""
        invite = self.get_invite(token)
        if invite and invite.is_valid:
            invite.current_uses += 1
            return True
        return False

    def store_device(self, device: RegisteredDevice) -> None:
        """Store a registered device"""
        self.devices[device.device_id] = device
        self.mesh_tokens[device.mesh_token_hash] = device.device_id

        # Set as primary if first device or explicitly primary
        if self.primary_device_id is None or device.assigned_role == NodeRole.PRIMARY:
            self.primary_device_id = device.device_id

    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        """Get device by ID"""
        return self.devices.get(device_id)

    def get_device_by_token(self, token: str) -> Optional[RegisteredDevice]:
        """Get device by mesh token"""
        token_hash = self._hash_token(token)
        device_id = self.mesh_tokens.get(token_hash)
        if device_id:
            return self.devices.get(device_id)
        return None

    def list_active_devices(self) -> list[RegisteredDevice]:
        """List all active devices"""
        return [
            d for d in self.devices.values()
            if d.status == NodeStatus.ACTIVE
        ]

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token for storage"""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def generate_token() -> tuple[str, str]:
        """Generate a secure token and its hash"""
        token = secrets.token_urlsafe(32)
        token_hash = BootstrapStore._hash_token(token)
        return token, token_hash


# Global store instance
_bootstrap_store: Optional[BootstrapStore] = None


def get_bootstrap_store() -> BootstrapStore:
    """Get the bootstrap store instance"""
    global _bootstrap_store
    if _bootstrap_store is None:
        _bootstrap_store = BootstrapStore()
    return _bootstrap_store


# === Dependencies ===

async def get_authenticated_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_mesh_token: Optional[str] = Header(default=None),
) -> RegisteredDevice:
    """
    Authenticate request using mesh token.

    Accepts token from either:
    - HTTPBearer (Authorization: Bearer <token>)
    - X-Mesh-Token header
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif x_mesh_token:
        token = x_mesh_token

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Mesh authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    store = get_bootstrap_store()
    device = store.get_device_by_token(token)

    if not device:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired mesh token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Update last seen
    device.last_seen = datetime.now(timezone.utc)

    return device


async def get_optional_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_mesh_token: Optional[str] = Header(default=None),
) -> Optional[RegisteredDevice]:
    """Get authenticated device if token provided, None otherwise"""
    token = credentials.credentials if credentials else x_mesh_token
    if not token:
        return None

    store = get_bootstrap_store()
    return store.get_device_by_token(token)


# === Health Check ===

@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Bootstrap server health check.

    Public endpoint - no authentication required.
    """
    store = get_bootstrap_store()
    wg = get_wireguard_generator()

    # Get server public key (this will generate keypair if not exists)
    server_keypair = wg.get_server_keypair()

    active_devices = store.list_active_devices()

    return {
        "status": "healthy",
        "service": "fog-bootstrap",
        "mesh_name": store.mesh_name,
        "mesh_cidr": store.mesh_cidr,
        "total_devices": len(store.devices),
        "active_devices": len(active_devices),
        "pending_invites": sum(1 for i in store.invites.values() if i.is_valid),
        "server_public_key": server_keypair.public_key,
        "primary_device_id": store.primary_device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# === Invite Management ===

@router.post("/invite", response_model=InviteResponse)
async def generate_invite(
    request: InviteRequest,
    req: Request,
    device: Optional[RegisteredDevice] = Depends(get_optional_device),
) -> InviteResponse:
    """
    Generate a QR code and invite link for mesh joining.

    Can be called by:
    - Authenticated PRIMARY device (normal operation)
    - Unauthenticated request (bootstrap mode for first device)

    Returns invite URL and QR codes (PNG base64 + SVG).
    """
    store = get_bootstrap_store()

    # If devices exist, only primary can create invites
    if store.devices and (device is None or device.assigned_role != NodeRole.PRIMARY):
        raise HTTPException(
            status_code=403,
            detail="Only the PRIMARY device can create invites"
        )

    # Generate invite token
    invite_token, token_hash = store.generate_token()

    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=request.expires_in_minutes)

    # Create invite record
    invite = InviteRecord(
        token=invite_token,
        token_hash=token_hash,
        mesh_name=request.mesh_name,
        intended_role=request.intended_role,
        expires_at=expires_at,
        max_uses=request.max_uses,
        allowed_ips=request.allowed_ips,
        note=request.note,
    )
    store.store_invite(invite)

    # Configure QR generator with actual server URL
    base_url = str(req.base_url).rstrip('/')
    qr_gen = configure_qr_generator(base_url)

    # Generate QR codes
    invite_url, png_base64, svg_string = qr_gen.generate_invite_qr(
        invite_token=invite_token,
        mesh_name=request.mesh_name,
        intended_role=request.intended_role.value,
    )

    logger.info(f"Generated invite for mesh '{request.mesh_name}', role={request.intended_role.value}")

    return InviteResponse(
        invite_token=invite_token,
        invite_url=invite_url,
        qr_code_base64=png_base64,
        qr_code_svg=svg_string,
        mesh_name=request.mesh_name,
        intended_role=request.intended_role,
        expires_at=expires_at,
        max_uses=request.max_uses,
        current_uses=0,
        bootstrap_server_url=base_url,
    )


@router.get("/invite/{token}", response_model=InviteStatusResponse)
async def get_invite_status(token: str) -> InviteStatusResponse:
    """
    Get the status of an invite token.

    Public endpoint for checking invite validity before registration.
    """
    store = get_bootstrap_store()
    invite = store.get_invite(token)

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    now = datetime.now(timezone.utc)

    return InviteStatusResponse(
        invite_token=token,
        is_valid=invite.is_valid,
        mesh_name=invite.mesh_name,
        intended_role=invite.intended_role,
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        current_uses=invite.current_uses,
        created_at=invite.created_at,
        is_expired=invite.expires_at <= now,
        remaining_uses=max(0, invite.max_uses - invite.current_uses),
    )


# === Device Registration ===

@router.post("/register", response_model=DeviceRegistrationResponse)
async def register_device(
    request: DeviceRegistrationRequest,
    req: Request,
) -> DeviceRegistrationResponse:
    """
    Register a new device in the mesh.

    Validates the invite token, generates mesh credentials,
    and allocates an IP address for the device.

    The device's WireGuard public key is stored for peer discovery.
    """
    store = get_bootstrap_store()
    wg = get_wireguard_generator()

    # Validate invite token
    invite = store.get_invite(request.invite_token)
    if not invite or not invite.is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired invite token"
        )

    # Validate public key format
    if not wg.validate_public_key(request.public_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid WireGuard public key format"
        )

    # Check if public key is already registered
    for device in store.devices.values():
        if device.public_key == request.public_key:
            raise HTTPException(
                status_code=409,
                detail="Device with this public key is already registered"
            )

    # Consume invite
    if not store.use_invite(request.invite_token):
        raise HTTPException(
            status_code=401,
            detail="Failed to use invite token"
        )

    # Generate device ID and mesh token
    device_id = f"fog-{secrets.token_hex(8)}"
    mesh_token, token_hash = store.generate_token()

    # Allocate IP address
    assigned_ip = store.allocate_ip()

    # Determine role - first device becomes PRIMARY
    assigned_role = invite.intended_role
    if not store.devices:
        assigned_role = NodeRole.PRIMARY
        logger.info(f"First device registered, assigning PRIMARY role")

    # Build endpoint from network info
    endpoint = None
    if request.network_info.endpoint:
        endpoint = request.network_info.endpoint
    elif request.network_info.public_ip and request.network_info.listen_port:
        endpoint = f"{request.network_info.public_ip}:{request.network_info.listen_port}"

    # Create device record
    device = RegisteredDevice(
        device_id=device_id,
        device_name=request.device_name,
        hostname=request.hostname,
        public_key=request.public_key,
        assigned_ip=assigned_ip,
        assigned_role=assigned_role,
        mesh_token=mesh_token,
        mesh_token_hash=token_hash,
        capabilities=request.capabilities,
        endpoint=endpoint,
        status=NodeStatus.ACTIVE,
    )
    store.store_device(device)

    # Get server keypair for peer info
    server_keypair = wg.get_server_keypair()

    # Build peer list (other devices in mesh)
    peer_endpoints = []
    for other_device in store.devices.values():
        if other_device.device_id != device_id:
            peer_endpoints.append({
                "device_id": other_device.device_id,
                "public_key": other_device.public_key,
                "endpoint": other_device.endpoint,
                "assigned_ip": other_device.assigned_ip,
            })

    # Get primary device info
    primary_endpoint = None
    primary_public_key = None
    if store.primary_device_id and store.primary_device_id != device_id:
        primary = store.devices.get(store.primary_device_id)
        if primary:
            primary_endpoint = primary.endpoint
            primary_public_key = primary.public_key

    logger.info(f"Registered device {device_id} ({request.device_name}) with IP {assigned_ip}")

    return DeviceRegistrationResponse(
        device_id=device_id,
        mesh_token=mesh_token,
        assigned_role=assigned_role,
        assigned_ip=assigned_ip,
        mesh_cidr=store.mesh_cidr,
        primary_node_endpoint=primary_endpoint,
        primary_node_public_key=primary_public_key,
        peer_endpoints=peer_endpoints,
        dns_servers=["10.0.0.1"],
        heartbeat_interval_sec=30,
    )


# === Key Exchange ===

@router.post("/exchange-keys", response_model=KeyExchangeResponse)
async def exchange_keys(
    request: KeyExchangeRequest,
    device: RegisteredDevice = Depends(get_authenticated_device),
) -> KeyExchangeResponse:
    """
    Exchange WireGuard keys with other mesh nodes.

    Returns peer information needed to establish WireGuard tunnels.
    Optionally targets a specific device or includes all relay nodes.
    """
    store = get_bootstrap_store()
    wg = get_wireguard_generator()

    # Validate the requester's device ID matches
    if request.device_id != device.device_id:
        raise HTTPException(
            status_code=403,
            detail="Device ID mismatch"
        )

    # Validate public key
    if not wg.validate_public_key(request.public_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid WireGuard public key format"
        )

    # Update device's public key if changed
    if device.public_key != request.public_key:
        logger.info(f"Device {device.device_id} updated public key")
        device.public_key = request.public_key

    # Build peer list
    peers: list[PeerKeyInfo] = []

    for other_device in store.devices.values():
        if other_device.device_id == device.device_id:
            continue

        # Filter by target device if specified
        if request.target_device_id and other_device.device_id != request.target_device_id:
            continue

        # Filter relay nodes if not requested
        is_relay = other_device.assigned_role == NodeRole.RELAY
        if not request.include_relay_nodes and is_relay:
            continue

        peers.append(PeerKeyInfo(
            device_id=other_device.device_id,
            device_name=other_device.device_name,
            public_key=other_device.public_key,
            endpoint=other_device.endpoint,
            allowed_ips=[f"{other_device.assigned_ip}/32"],
            persistent_keepalive=25,
            role=other_device.assigned_role,
            is_relay=is_relay,
        ))

    # Get server public key
    server_keypair = wg.get_server_keypair()

    logger.debug(f"Key exchange for device {device.device_id}: {len(peers)} peers")

    return KeyExchangeResponse(
        success=True,
        your_device_id=device.device_id,
        your_assigned_ip=device.assigned_ip,
        peers=peers,
        server_public_key=server_keypair.public_key,
    )


# === Node Discovery ===

@router.get("/discover", response_model=NodeDiscoveryResponse)
async def discover_nodes(
    device: RegisteredDevice = Depends(get_authenticated_device),
    include_inactive: bool = Query(default=False, description="Include inactive nodes"),
    role: Optional[NodeRole] = Query(default=None, description="Filter by role"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum nodes to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> NodeDiscoveryResponse:
    """
    Discover nodes in the mesh network.

    Returns a list of known nodes with their connection information.
    Requires authentication.
    """
    store = get_bootstrap_store()

    # Get all devices
    all_devices = list(store.devices.values())

    # Filter by status
    if not include_inactive:
        all_devices = [d for d in all_devices if d.status == NodeStatus.ACTIVE]

    # Filter by role
    if role:
        all_devices = [d for d in all_devices if d.assigned_role == role]

    # Count totals before pagination
    total_nodes = len(store.devices)
    active_nodes = sum(1 for d in store.devices.values() if d.status == NodeStatus.ACTIVE)

    # Apply pagination
    paginated = all_devices[offset:offset + limit]

    # Build response nodes
    nodes: list[DiscoveredNode] = []
    now = datetime.now(timezone.utc)

    for dev in paginated:
        # Calculate time since last seen
        last_seen_delta = (now - dev.last_seen).total_seconds()
        is_reachable = last_seen_delta < 120  # 2 minutes threshold

        nodes.append(DiscoveredNode(
            device_id=dev.device_id,
            device_name=dev.device_name,
            hostname=dev.hostname,
            role=dev.assigned_role,
            status=dev.status,
            public_key=dev.public_key,
            endpoint=dev.endpoint,
            assigned_ip=dev.assigned_ip,
            capabilities=dev.capabilities,
            last_seen=dev.last_seen,
            latency_ms=None,  # Would need active probing
            is_reachable=is_reachable,
            zone="default",
        ))

    # Calculate mesh health (simple ratio of active/total)
    mesh_health = active_nodes / total_nodes if total_nodes > 0 else 1.0

    return NodeDiscoveryResponse(
        mesh_name=store.mesh_name,
        total_nodes=total_nodes,
        active_nodes=active_nodes,
        primary_node_id=store.primary_device_id,
        nodes=nodes,
        mesh_health_score=round(mesh_health, 2),
    )


# === WireGuard Config Generation ===

@router.get("/config/{device_id}")
async def get_wireguard_config(
    device_id: str,
    device: RegisteredDevice = Depends(get_authenticated_device),
) -> dict[str, Any]:
    """
    Get WireGuard configuration for a device.

    Only the device owner can request their own config.
    Returns configuration snippet (without private key for security).
    """
    if device_id != device.device_id:
        raise HTTPException(
            status_code=403,
            detail="Can only request your own configuration"
        )

    store = get_bootstrap_store()
    wg = get_wireguard_generator()

    # Build peer list
    peers = []
    for other_device in store.devices.values():
        if other_device.device_id == device.device_id:
            continue

        peer_config = {
            "public_key": other_device.public_key,
            "allowed_ips": [f"{other_device.assigned_ip}/32"],
            "persistent_keepalive": 25,
        }

        if other_device.endpoint:
            peer_config["endpoint"] = other_device.endpoint

        peers.append(peer_config)

    # Generate config (without private key - that stays on device)
    # This is a template that the device can use
    config_template = {
        "interface": {
            "address": f"{device.assigned_ip}/24",
            "listen_port": 51820,
            "dns": ["10.0.0.1"],
            # Private key should be generated/stored locally
            "private_key": "< YOUR_PRIVATE_KEY >",
        },
        "peers": peers,
        "mesh_cidr": store.mesh_cidr,
        "mesh_name": store.mesh_name,
    }

    return {
        "device_id": device_id,
        "config": config_template,
        "peer_count": len(peers),
        "note": "Replace < YOUR_PRIVATE_KEY > with your actual WireGuard private key",
    }
