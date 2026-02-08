"""
WireGuard Key Generation
========================

FOG-INSTALL-005: WireGuard keypair generation for mesh tunnel establishment.

Uses the cryptography library to generate Curve25519 keypairs compatible
with WireGuard's key format.

WireGuard keys are:
- 32 bytes (256 bits) Curve25519 keys
- Base64 encoded (44 characters with padding)
- Private key is clamped per Curve25519 spec

Security Notes:
- Private keys should NEVER be stored in logs or transmitted over network
- Keys should be generated on the device that will use them
- This module is for bootstrap server's own key and for key validation only
"""
from __future__ import annotations

import base64
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization

from .models import WireGuardKeyPair

logger = logging.getLogger(__name__)


class WireGuardKeyGenerator:
    """
    WireGuard key generation and validation service.

    Generates Curve25519 keypairs compatible with WireGuard.
    """

    # WireGuard key constants
    KEY_LENGTH_BYTES = 32
    KEY_LENGTH_BASE64 = 44  # 32 bytes -> 44 base64 chars (with padding)

    def __init__(self):
        """Initialize the key generator."""
        self._server_keypair: Optional[WireGuardKeyPair] = None

    def generate_keypair(self) -> WireGuardKeyPair:
        """
        Generate a new WireGuard-compatible Curve25519 keypair.

        Returns:
            WireGuardKeyPair with public and private keys in base64 format

        Security Note:
            The private key returned should be handled securely and never logged.
        """
        # Generate a new X25519 private key
        private_key = X25519PrivateKey.generate()

        # Get the public key
        public_key = private_key.public_key()

        # Serialize to raw bytes
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        # Encode to base64 (WireGuard format)
        private_b64 = base64.b64encode(private_bytes).decode('ascii')
        public_b64 = base64.b64encode(public_bytes).decode('ascii')

        logger.debug(f"Generated new WireGuard keypair (public: {public_b64[:8]}...)")

        return WireGuardKeyPair(
            public_key=public_b64,
            private_key=private_b64,
            created_at=datetime.now(timezone.utc)
        )

    def generate_preshared_key(self) -> str:
        """
        Generate a WireGuard preshared key.

        Preshared keys add an additional layer of symmetric-key cryptography
        to WireGuard connections for post-quantum resistance.

        Returns:
            Base64-encoded 32-byte preshared key
        """
        # Generate 32 random bytes
        psk_bytes = secrets.token_bytes(self.KEY_LENGTH_BYTES)
        return base64.b64encode(psk_bytes).decode('ascii')

    def validate_public_key(self, public_key: str) -> bool:
        """
        Validate a WireGuard public key format.

        Args:
            public_key: Base64-encoded public key string

        Returns:
            True if key is valid format, False otherwise
        """
        try:
            # Decode from base64
            key_bytes = base64.b64decode(public_key)

            # Check length (must be exactly 32 bytes)
            if len(key_bytes) != self.KEY_LENGTH_BYTES:
                logger.warning(f"Invalid key length: {len(key_bytes)} bytes (expected {self.KEY_LENGTH_BYTES})")
                return False

            # Try to load as X25519 public key to validate format
            X25519PublicKey.from_public_bytes(key_bytes)

            return True

        except Exception as e:
            logger.warning(f"Invalid public key format: {e}")
            return False

    def validate_private_key(self, private_key: str) -> bool:
        """
        Validate a WireGuard private key format.

        Args:
            private_key: Base64-encoded private key string

        Returns:
            True if key is valid format, False otherwise

        Security Note:
            This method should only be used for local key validation.
            Never validate private keys received over the network.
        """
        try:
            # Decode from base64
            key_bytes = base64.b64decode(private_key)

            # Check length
            if len(key_bytes) != self.KEY_LENGTH_BYTES:
                return False

            # Try to load as X25519 private key
            X25519PrivateKey.from_private_bytes(key_bytes)

            return True

        except Exception as e:
            logger.debug(f"Invalid private key format: {e}")
            return False

    def derive_public_key(self, private_key: str) -> str:
        """
        Derive the public key from a private key.

        Args:
            private_key: Base64-encoded private key

        Returns:
            Base64-encoded public key

        Raises:
            ValueError: If private key is invalid
        """
        try:
            # Decode private key
            private_bytes = base64.b64decode(private_key)

            # Load as X25519 private key
            priv_key = X25519PrivateKey.from_private_bytes(private_bytes)

            # Get public key
            pub_key = priv_key.public_key()

            # Serialize to raw bytes and encode
            pub_bytes = pub_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            return base64.b64encode(pub_bytes).decode('ascii')

        except Exception as e:
            raise ValueError(f"Failed to derive public key: {e}")

    def get_server_keypair(self) -> WireGuardKeyPair:
        """
        Get or generate the bootstrap server's WireGuard keypair.

        The server keypair is cached for the lifetime of the service.
        In production, this should be loaded from secure storage.

        Returns:
            WireGuardKeyPair for the bootstrap server
        """
        if self._server_keypair is None:
            logger.info("Generating bootstrap server WireGuard keypair")
            self._server_keypair = self.generate_keypair()
            # Log public key only (never log private key!)
            logger.info(f"Server public key: {self._server_keypair.public_key}")

        return self._server_keypair

    def set_server_keypair(self, keypair: WireGuardKeyPair) -> None:
        """
        Set the server keypair from external configuration.

        Use this to load a pre-existing keypair from secure storage.

        Args:
            keypair: The keypair to use for the bootstrap server
        """
        if not self.validate_public_key(keypair.public_key):
            raise ValueError("Invalid public key in keypair")

        if not self.validate_private_key(keypair.private_key):
            raise ValueError("Invalid private key in keypair")

        self._server_keypair = keypair
        logger.info(f"Server keypair loaded (public: {keypair.public_key[:8]}...)")

    @staticmethod
    def generate_config_snippet(
        private_key: str,
        address: str,
        peers: list[dict],
        listen_port: int = 51820,
        dns: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a WireGuard configuration file snippet.

        Args:
            private_key: This node's private key
            address: Assigned IP address in CIDR notation (e.g., "10.0.0.2/24")
            peers: List of peer configurations
            listen_port: WireGuard listen port
            dns: Optional DNS server list

        Returns:
            WireGuard configuration file content

        Example peer format:
            {
                "public_key": "base64-public-key",
                "endpoint": "1.2.3.4:51820",  # Optional
                "allowed_ips": ["10.0.0.0/24"],
                "persistent_keepalive": 25  # Optional
            }
        """
        lines = [
            "[Interface]",
            f"PrivateKey = {private_key}",
            f"Address = {address}",
            f"ListenPort = {listen_port}",
        ]

        if dns:
            lines.append(f"DNS = {', '.join(dns)}")

        for peer in peers:
            lines.extend([
                "",
                "[Peer]",
                f"PublicKey = {peer['public_key']}",
            ])

            if peer.get('endpoint'):
                lines.append(f"Endpoint = {peer['endpoint']}")

            if peer.get('allowed_ips'):
                lines.append(f"AllowedIPs = {', '.join(peer['allowed_ips'])}")

            if peer.get('persistent_keepalive'):
                lines.append(f"PersistentKeepalive = {peer['persistent_keepalive']}")

            if peer.get('preshared_key'):
                lines.append(f"PresharedKey = {peer['preshared_key']}")

        return "\n".join(lines) + "\n"


# Module-level singleton instance
_key_generator: Optional[WireGuardKeyGenerator] = None


def get_wireguard_generator() -> WireGuardKeyGenerator:
    """Get the singleton WireGuardKeyGenerator instance."""
    global _key_generator
    if _key_generator is None:
        _key_generator = WireGuardKeyGenerator()
    return _key_generator
