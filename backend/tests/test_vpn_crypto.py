"""
Unit tests for VPN onion routing cryptographic functions.

Tests the critical encrypt/decrypt round-trip functionality with proper nonce handling.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vpn.onion_routing import (
    OnionRouter,
    OnionCircuit,
    CircuitState,
    NodeType,
    CircuitHop,
    OnionNode,
)
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets


@pytest.fixture
def onion_router():
    """Create an onion router instance for testing"""
    router = OnionRouter(
        node_id="test-router-1",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )
    return router


@pytest.fixture
def test_circuit(onion_router):
    """Create a test circuit with 3 hops"""
    circuit = OnionCircuit(
        circuit_id="test-circuit-123",
        state=CircuitState.ESTABLISHED,
        hops=[],
    )

    # Create 3 test hops
    for i in range(3):
        node = OnionNode(
            node_id=f"test-node-{i}",
            address=f"10.0.0.{i}:9001",
            node_types={NodeType.MIDDLE},
            identity_key=ed25519.Ed25519PrivateKey.generate()
            .public_key()
            .public_bytes(
                encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
            ),
            onion_key=x25519.X25519PrivateKey.generate()
            .public_key()
            .public_bytes(
                encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
            ),
        )

        # Generate shared secret and derive keys
        shared_secret = secrets.token_bytes(32)
        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=b"fog-onion-v1",
            info=b"circuit-keys",
            backend=default_backend(),
        )
        key_material = kdf.derive(shared_secret)

        hop = CircuitHop(
            node=node,
            position=i,
            shared_secret=shared_secret,
            forward_key=key_material[:16],
            backward_key=key_material[16:32],
            forward_digest=key_material[32:48],
            backward_digest=key_material[48:64],
            circuit_id=i,
        )

        circuit.hops.append(hop)

    return circuit


class TestCryptoFunctions:
    """Test cryptographic functions in onion routing"""

    def test_encrypt_decrypt_round_trip(self, onion_router, test_circuit):
        """Test that encryption followed by decryption recovers original payload"""
        # Original payload
        original_payload = b"Hello, this is a test message for onion routing!"

        # Encrypt the payload
        encrypted = onion_router._onion_encrypt(test_circuit, original_payload)

        # Verify encrypted data is different from original
        assert encrypted != original_payload

        # Verify encrypted data is longer (includes nonce + mac for each hop)
        # Each hop adds: 16 bytes (nonce) + 4 bytes (mac) = 20 bytes per hop
        # Plus padding to cell_size (512 bytes default)
        assert len(encrypted) >= len(original_payload)

        # Decrypt layer by layer (in forward order)
        decrypted = encrypted
        for hop_index in range(len(test_circuit.hops)):
            decrypted = onion_router._onion_decrypt(test_circuit, decrypted, hop_index)

        # Remove padding
        final_payload = onion_router._unpad_payload(decrypted)

        # Verify we got back the original payload
        assert final_payload == original_payload

    def test_multi_hop_circuit(self, onion_router, test_circuit):
        """Test multi-hop encryption with different payloads"""
        payloads = [
            b"Short message",
            b"A" * 100,  # Medium message
            b"B" * 500,  # Large message
            b"\x00\x01\x02\x03\x04",  # Binary data
        ]

        for payload in payloads:
            # Encrypt
            encrypted = onion_router._onion_encrypt(test_circuit, payload)

            # Decrypt all layers
            decrypted = encrypted
            for hop_index in range(len(test_circuit.hops)):
                decrypted = onion_router._onion_decrypt(test_circuit, decrypted, hop_index)

            # Verify
            final_payload = onion_router._unpad_payload(decrypted)
            assert final_payload == payload, f"Failed for payload length {len(payload)}"

    def test_invalid_mac_rejection(self, onion_router, test_circuit):
        """Test that tampered data is rejected due to MAC verification failure"""
        original_payload = b"This message will be tampered with"

        # Encrypt the payload
        encrypted = onion_router._onion_encrypt(test_circuit, original_payload)

        # Tamper with the encrypted data (flip a bit in the ciphertext part)
        # Structure is: nonce(16) + mac(4) + ciphertext
        tampered = bytearray(encrypted)
        tampered[25] ^= 0xFF  # Flip a byte in the ciphertext
        tampered = bytes(tampered)

        # Attempt to decrypt should raise ValueError due to MAC mismatch
        with pytest.raises(ValueError, match="Integrity check failed"):
            onion_router._onion_decrypt(test_circuit, tampered, 0)

    def test_nonce_uniqueness(self, onion_router, test_circuit):
        """Test that each encryption uses a different nonce"""
        payload = b"Test message for nonce uniqueness"

        # Encrypt the same payload twice
        encrypted1 = onion_router._onion_encrypt(test_circuit, payload)
        encrypted2 = onion_router._onion_encrypt(test_circuit, payload)

        # The encrypted outputs should be different (different nonces)
        assert encrypted1 != encrypted2

        # But both should decrypt to the same payload
        decrypted1 = encrypted1
        decrypted2 = encrypted2

        for hop_index in range(len(test_circuit.hops)):
            decrypted1 = onion_router._onion_decrypt(test_circuit, decrypted1, hop_index)
            decrypted2 = onion_router._onion_decrypt(test_circuit, decrypted2, hop_index)

        final1 = onion_router._unpad_payload(decrypted1)
        final2 = onion_router._unpad_payload(decrypted2)

        assert final1 == payload
        assert final2 == payload

    def test_empty_payload(self, onion_router, test_circuit):
        """Test encryption/decryption of empty payload"""
        payload = b""

        encrypted = onion_router._onion_encrypt(test_circuit, payload)

        # Decrypt all layers
        decrypted = encrypted
        for hop_index in range(len(test_circuit.hops)):
            decrypted = onion_router._onion_decrypt(test_circuit, decrypted, hop_index)

        final_payload = onion_router._unpad_payload(decrypted)
        assert final_payload == payload

    def test_encrypted_data_too_short(self, onion_router, test_circuit):
        """Test that decryption rejects data shorter than minimum size"""
        # Data must be at least 20 bytes (16 nonce + 4 mac)
        too_short = b"short"

        with pytest.raises(ValueError, match="Encrypted data too short"):
            onion_router._onion_decrypt(test_circuit, too_short, 0)

    def test_single_hop_decrypt(self, onion_router, test_circuit):
        """Test decrypting a single hop at a time"""
        payload = b"Test partial decryption"

        encrypted = onion_router._onion_encrypt(test_circuit, payload)

        # Decrypt first hop only
        after_hop0 = onion_router._onion_decrypt(test_circuit, encrypted, 0)

        # Should still be encrypted (2 more layers)
        assert after_hop0 != payload

        # Decrypt second hop
        after_hop1 = onion_router._onion_decrypt(test_circuit, after_hop0, 1)

        # Still encrypted (1 more layer)
        assert after_hop1 != payload

        # Decrypt third hop
        after_hop2 = onion_router._onion_decrypt(test_circuit, after_hop1, 2)

        # Now we should have the padded plaintext
        final_payload = onion_router._unpad_payload(after_hop2)
        assert final_payload == payload

    def test_padding_correctness(self, onion_router):
        """Test that padding is applied and removed correctly"""
        test_cases = [
            b"A" * 100,
            b"B" * 511,
            b"C" * 512,
            b"D" * 513,
        ]

        for payload in test_cases:
            padded = onion_router._pad_payload(payload)

            # Padded size should be multiple of 512
            assert len(padded) % 512 == 0

            # Unpadding should recover original
            unpadded = onion_router._unpad_payload(padded)
            assert unpadded == payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
