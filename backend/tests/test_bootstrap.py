"""
Bootstrap Server Tests
======================

FOG-INSTALL-005: Tests for mesh bootstrap functionality.

Tests cover:
- Invite generation and QR code creation
- Device registration with profile
- WireGuard key exchange
- Node discovery
"""
import pytest
import base64
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import bootstrap components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bootstrap.models import (
    InviteRequest,
    InviteResponse,
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    KeyExchangeRequest,
    KeyExchangeResponse,
    NodeDiscoveryResponse,
    NodeRole,
    NodeStatus,
    DeviceCapabilities,
    NetworkInfo,
    WireGuardKeyPair,
)
from bootstrap.wireguard import WireGuardKeyGenerator, get_wireguard_generator
from bootstrap.qr import QRCodeGenerator, get_qr_generator
from bootstrap.router import router, get_bootstrap_store, BootstrapStore


# === Fixtures ===

@pytest.fixture
def fastapi_app():
    """Create a test FastAPI application"""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(fastapi_app):
    """Create a test client"""
    return TestClient(fastapi_app)


@pytest.fixture
def fresh_store():
    """Reset bootstrap store for each test"""
    import bootstrap.router as router_module
    router_module._bootstrap_store = None
    store = get_bootstrap_store()
    # Defensive reset in case another module holds a reference.
    store.invites.clear()
    store.devices.clear()
    store.mesh_tokens.clear()
    store.ip_allocations.clear()
    store.next_ip_offset = 2
    store.primary_device_id = None
    store.mesh_name = "fog-mesh"
    store.mesh_cidr = "10.0.0.0/24"
    yield store
    router_module._bootstrap_store = None


@pytest.fixture
def wireguard_gen():
    """Get WireGuard key generator"""
    return WireGuardKeyGenerator()


@pytest.fixture
def qr_gen():
    """Get QR code generator"""
    return QRCodeGenerator(base_url="http://localhost:8000")


# === WireGuard Key Tests ===

class TestWireGuardKeyGenerator:
    """Tests for WireGuard key generation"""

    def test_generate_keypair(self, wireguard_gen):
        """Test keypair generation"""
        keypair = wireguard_gen.generate_keypair()

        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert len(keypair.public_key) == 44  # Base64 of 32 bytes
        assert len(keypair.private_key) == 44
        assert keypair.created_at is not None

    def test_keypair_valid_base64(self, wireguard_gen):
        """Test that keys are valid base64"""
        keypair = wireguard_gen.generate_keypair()

        # Should decode without error
        public_bytes = base64.b64decode(keypair.public_key)
        private_bytes = base64.b64decode(keypair.private_key)

        assert len(public_bytes) == 32
        assert len(private_bytes) == 32

    def test_unique_keypairs(self, wireguard_gen):
        """Test that each keypair is unique"""
        keypairs = [wireguard_gen.generate_keypair() for _ in range(5)]

        public_keys = [kp.public_key for kp in keypairs]
        private_keys = [kp.private_key for kp in keypairs]

        assert len(set(public_keys)) == 5
        assert len(set(private_keys)) == 5

    def test_validate_public_key(self, wireguard_gen):
        """Test public key validation"""
        keypair = wireguard_gen.generate_keypair()

        assert wireguard_gen.validate_public_key(keypair.public_key) is True
        assert wireguard_gen.validate_public_key("invalid-key") is False
        assert wireguard_gen.validate_public_key("") is False
        assert wireguard_gen.validate_public_key("abc") is False

    def test_validate_private_key(self, wireguard_gen):
        """Test private key validation"""
        keypair = wireguard_gen.generate_keypair()

        assert wireguard_gen.validate_private_key(keypair.private_key) is True
        assert wireguard_gen.validate_private_key("invalid-key") is False

    def test_derive_public_key(self, wireguard_gen):
        """Test deriving public key from private key"""
        keypair = wireguard_gen.generate_keypair()

        derived_public = wireguard_gen.derive_public_key(keypair.private_key)

        assert derived_public == keypair.public_key

    def test_generate_preshared_key(self, wireguard_gen):
        """Test preshared key generation"""
        psk = wireguard_gen.generate_preshared_key()

        assert len(psk) == 44  # Base64 of 32 bytes
        decoded = base64.b64decode(psk)
        assert len(decoded) == 32

    def test_server_keypair_caching(self, wireguard_gen):
        """Test that server keypair is cached"""
        keypair1 = wireguard_gen.get_server_keypair()
        keypair2 = wireguard_gen.get_server_keypair()

        assert keypair1.public_key == keypair2.public_key
        assert keypair1.private_key == keypair2.private_key

    def test_config_snippet_generation(self, wireguard_gen):
        """Test WireGuard config snippet generation"""
        keypair = wireguard_gen.generate_keypair()

        config = wireguard_gen.generate_config_snippet(
            private_key=keypair.private_key,
            address="10.0.0.2/24",
            peers=[
                {
                    "public_key": wireguard_gen.generate_keypair().public_key,
                    "endpoint": "1.2.3.4:51820",
                    "allowed_ips": ["10.0.0.0/24"],
                    "persistent_keepalive": 25,
                }
            ],
            listen_port=51820,
            dns=["10.0.0.1"],
        )

        assert "[Interface]" in config
        assert "[Peer]" in config
        assert keypair.private_key in config
        assert "10.0.0.2/24" in config


# === QR Code Tests ===

class TestQRCodeGenerator:
    """Tests for QR code generation"""

    def test_generate_invite_url(self, qr_gen):
        """Test invite URL generation"""
        url = qr_gen.generate_invite_url(
            invite_token="test-token-123",
            mesh_name="fog-mesh",
            intended_role="worker",
        )

        assert "http://localhost:8000" in url
        assert "token=test-token-123" in url
        assert "mesh=fog-mesh" in url
        assert "role=worker" in url

    def test_generate_png_base64(self, qr_gen):
        """Test PNG QR code generation"""
        png_b64 = qr_gen.generate_png_base64("test-data")

        # Should be valid base64
        decoded = base64.b64decode(png_b64)
        # PNG magic bytes
        assert decoded[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_svg(self, qr_gen):
        """Test SVG QR code generation"""
        svg = qr_gen.generate_svg("test-data")

        assert "<?xml" in svg or "<svg" in svg
        assert "svg" in svg.lower()

    def test_generate_invite_qr(self, qr_gen):
        """Test full invite QR generation"""
        url, png, svg = qr_gen.generate_invite_qr(
            invite_token="test-token",
            mesh_name="fog-mesh",
            intended_role="worker",
        )

        assert "token=test-token" in url
        assert len(png) > 0
        assert len(svg) > 0


# === API Endpoint Tests ===

class TestBootstrapAPI:
    """Tests for bootstrap API endpoints"""

    def test_health_check(self, client, fresh_store):
        """Test health check endpoint"""
        response = client.get("/api/v1/bootstrap/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "fog-bootstrap"
        assert "server_public_key" in data

    def test_create_invite_first_device(self, client, fresh_store):
        """Test creating invite for first device (no auth required)"""
        response = client.post(
            "/api/v1/bootstrap/invite",
            json={
                "mesh_name": "test-mesh",
                "expires_in_minutes": 30,
                "intended_role": "worker",
                "max_uses": 1,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "invite_token" in data
        assert "invite_url" in data
        assert "qr_code_base64" in data
        assert "qr_code_svg" in data
        assert data["mesh_name"] == "test-mesh"
        assert data["max_uses"] == 1

    def test_get_invite_status(self, client, fresh_store):
        """Test getting invite status"""
        # First create an invite
        create_response = client.post(
            "/api/v1/bootstrap/invite",
            json={"mesh_name": "test-mesh"}
        )
        token = create_response.json()["invite_token"]

        # Get its status
        response = client.get(f"/api/v1/bootstrap/invite/{token}")

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["mesh_name"] == "test-mesh"
        assert data["remaining_uses"] == 1

    def test_get_invalid_invite_status(self, client, fresh_store):
        """Test getting status of non-existent invite"""
        response = client.get("/api/v1/bootstrap/invite/invalid-token")
        assert response.status_code == 404

    def test_register_device(self, client, fresh_store, wireguard_gen):
        """Test device registration"""
        # Create invite
        invite_response = client.post(
            "/api/v1/bootstrap/invite",
            json={"mesh_name": "test-mesh"}
        )
        invite_token = invite_response.json()["invite_token"]

        # Generate a keypair
        keypair = wireguard_gen.generate_keypair()

        # Register device
        response = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": invite_token,
                "device_name": "test-device",
                "hostname": "test-host",
                "public_key": keypair.public_key,
                "capabilities": {
                    "cpu_cores": 4,
                    "ram_gb": 8.0,
                },
                "network_info": {
                    "listen_port": 51820,
                },
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "device_id" in data
        assert "mesh_token" in data
        assert data["assigned_ip"].startswith("10.0.0.")
        assert data["mesh_cidr"] == "10.0.0.0/24"

    def test_register_first_device_becomes_primary(self, client, fresh_store, wireguard_gen):
        """Test that first device becomes PRIMARY"""
        # Create invite with worker role
        invite_response = client.post(
            "/api/v1/bootstrap/invite",
            json={"mesh_name": "test-mesh", "intended_role": "worker"}
        )
        invite_token = invite_response.json()["invite_token"]

        keypair = wireguard_gen.generate_keypair()

        response = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": invite_token,
                "device_name": "first-device",
                "hostname": "first-host",
                "public_key": keypair.public_key,
            }
        )

        assert response.status_code == 200
        # First device should be PRIMARY regardless of invite role
        assert response.json()["assigned_role"] == "primary"

    def test_register_invalid_invite(self, client, fresh_store, wireguard_gen):
        """Test registration with invalid invite"""
        keypair = wireguard_gen.generate_keypair()

        response = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": "invalid-token-12345678901234567890",
                "device_name": "test-device",
                "hostname": "test-host",
                "public_key": keypair.public_key,
            }
        )

        assert response.status_code == 401

    def test_register_invalid_public_key(self, client, fresh_store):
        """Test registration with invalid public key"""
        invite_response = client.post(
            "/api/v1/bootstrap/invite",
            json={"mesh_name": "test-mesh"}
        )
        invite_token = invite_response.json()["invite_token"]

        response = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": invite_token,
                "device_name": "test-device",
                "hostname": "test-host",
                "public_key": "invalid-not-base64-key",
            }
        )

        assert response.status_code == 422  # Validation error

    def test_key_exchange(self, client, fresh_store, wireguard_gen):
        """Test key exchange between nodes"""
        # Register first device
        invite1 = client.post("/api/v1/bootstrap/invite", json={}).json()
        keypair1 = wireguard_gen.generate_keypair()
        device1 = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": invite1["invite_token"],
                "device_name": "device1",
                "hostname": "host1",
                "public_key": keypair1.public_key,
            }
        ).json()

        # Register second device
        invite2 = client.post(
            "/api/v1/bootstrap/invite",
            headers={"Authorization": f"Bearer {device1['mesh_token']}"},
            json={}
        ).json()
        keypair2 = wireguard_gen.generate_keypair()
        device2 = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": invite2["invite_token"],
                "device_name": "device2",
                "hostname": "host2",
                "public_key": keypair2.public_key,
            }
        ).json()

        # Exchange keys as device2
        response = client.post(
            "/api/v1/bootstrap/exchange-keys",
            headers={"Authorization": f"Bearer {device2['mesh_token']}"},
            json={
                "device_id": device2["device_id"],
                "mesh_token": device2["mesh_token"],
                "public_key": keypair2.public_key,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["peers"]) == 1
        assert data["peers"][0]["device_id"] == device1["device_id"]

    def test_discover_nodes(self, client, fresh_store, wireguard_gen):
        """Test node discovery"""
        # Register a device first
        invite = client.post("/api/v1/bootstrap/invite", json={}).json()
        keypair = wireguard_gen.generate_keypair()
        device = client.post(
            "/api/v1/bootstrap/register",
            json={
                "invite_token": invite["invite_token"],
                "device_name": "test-device",
                "hostname": "test-host",
                "public_key": keypair.public_key,
            }
        ).json()

        # Discover nodes
        response = client.get(
            "/api/v1/bootstrap/discover",
            headers={"Authorization": f"Bearer {device['mesh_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 1
        assert data["active_nodes"] == 1
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["device_name"] == "test-device"

    def test_discover_unauthenticated(self, client, fresh_store):
        """Test that discovery requires authentication"""
        response = client.get("/api/v1/bootstrap/discover")
        assert response.status_code == 401


# === Bootstrap Store Tests ===

class TestBootstrapStore:
    """Tests for the in-memory bootstrap store"""

    def test_ip_allocation(self, fresh_store):
        """Test IP address allocation"""
        ip1 = fresh_store.allocate_ip()
        ip2 = fresh_store.allocate_ip()
        ip3 = fresh_store.allocate_ip()

        # Allocations should be unique and sequential.
        assert len({ip1, ip2, ip3}) == 3
        assert all(ip.startswith("10.0.0.") for ip in [ip1, ip2, ip3])
        last_octets = [int(ip.split(".")[-1]) for ip in [ip1, ip2, ip3]]
        assert last_octets[1] == last_octets[0] + 1
        assert last_octets[2] == last_octets[1] + 1

    def test_token_generation(self, fresh_store):
        """Test token generation"""
        token, token_hash = fresh_store.generate_token()

        assert len(token) > 20
        assert len(token_hash) == 64  # SHA-256 hex

    def test_invite_lifecycle(self, fresh_store, wireguard_gen):
        """Test invite creation, validation, and consumption"""
        from bootstrap.router import InviteRecord

        token, token_hash = fresh_store.generate_token()
        invite = InviteRecord(
            token=token,
            token_hash=token_hash,
            mesh_name="test",
            intended_role=NodeRole.WORKER,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            max_uses=2,
        )
        fresh_store.store_invite(invite)

        # Should be valid
        retrieved = fresh_store.get_invite(token)
        assert retrieved is not None
        assert retrieved.is_valid is True

        # Use once
        assert fresh_store.use_invite(token) is True
        assert retrieved.current_uses == 1
        assert retrieved.is_valid is True

        # Use twice
        assert fresh_store.use_invite(token) is True
        assert retrieved.current_uses == 2
        assert retrieved.is_valid is False  # Max uses reached

        # Can't use anymore
        assert fresh_store.use_invite(token) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
