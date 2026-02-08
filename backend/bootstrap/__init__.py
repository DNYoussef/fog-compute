"""
Mesh Bootstrap Server
=====================

FOG-INSTALL-005: Mesh Bootstrap Server for fog-compute

This module provides mesh discovery and bootstrap functionality:
- QR code/invite link generation for mesh joining
- Device registration with profile validation
- WireGuard key exchange for secure tunnel establishment
- Node discovery for mesh topology awareness

Endpoints:
- POST /api/v1/bootstrap/invite      - Generate QR code/invite link for mesh join
- POST /api/v1/bootstrap/register    - Device registration with profile
- POST /api/v1/bootstrap/exchange-keys - WireGuard key exchange
- GET  /api/v1/bootstrap/discover    - Return list of known nodes
"""

from .router import router
from .models import (
    InviteRequest,
    InviteResponse,
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    KeyExchangeRequest,
    KeyExchangeResponse,
    NodeDiscoveryResponse,
    DiscoveredNode,
    WireGuardKeyPair,
)
from .wireguard import WireGuardKeyGenerator
from .qr import QRCodeGenerator

__all__ = [
    # Router
    "router",
    # Models
    "InviteRequest",
    "InviteResponse",
    "DeviceRegistrationRequest",
    "DeviceRegistrationResponse",
    "KeyExchangeRequest",
    "KeyExchangeResponse",
    "NodeDiscoveryResponse",
    "DiscoveredNode",
    "WireGuardKeyPair",
    # Services
    "WireGuardKeyGenerator",
    "QRCodeGenerator",
]
