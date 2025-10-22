"""
Standalone test runner for VPN crypto functionality.
Tests the critical encrypt/decrypt round-trip without pytest dependency.
"""

import sys
import io
from pathlib import Path
import traceback

# Fix Windows console encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

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


def create_test_circuit():
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


def test_encrypt_decrypt_round_trip():
    """Test that encryption followed by decryption recovers original payload"""
    print("TEST: Encrypt/Decrypt Round Trip")

    router = OnionRouter(
        node_id="test-router-1",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    circuit = create_test_circuit()

    # Original payload
    original_payload = b"Hello, this is a test message for onion routing!"

    # Encrypt the payload
    encrypted = router._onion_encrypt(circuit, original_payload)

    # Verify encrypted data is different from original
    assert encrypted != original_payload, "Encrypted data should differ from original"

    # Verify encrypted data is longer
    assert len(encrypted) >= len(original_payload), "Encrypted data should be longer"

    # Decrypt layer by layer (in forward order)
    decrypted = encrypted
    for hop_index in range(len(circuit.hops)):
        decrypted = router._onion_decrypt(circuit, decrypted, hop_index)

    # Remove padding
    final_payload = router._unpad_payload(decrypted)

    # Verify we got back the original payload
    assert final_payload == original_payload, "Decrypted payload should match original"

    print("  PASS: Round trip successful")
    return True


def test_multi_hop_circuit():
    """Test multi-hop encryption with different payloads"""
    print("TEST: Multi-Hop Circuit")

    router = OnionRouter(
        node_id="test-router-2",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    circuit = create_test_circuit()

    payloads = [
        b"Short message",
        b"A" * 100,  # Medium message
        b"B" * 500,  # Large message
        b"\x00\x01\x02\x03\x04",  # Binary data
    ]

    for payload in payloads:
        # Encrypt
        encrypted = router._onion_encrypt(circuit, payload)

        # Decrypt all layers
        decrypted = encrypted
        for hop_index in range(len(circuit.hops)):
            decrypted = router._onion_decrypt(circuit, decrypted, hop_index)

        # Verify
        final_payload = router._unpad_payload(decrypted)
        assert final_payload == payload, f"Failed for payload length {len(payload)}"

    print(f"  ✅ PASS: {len(payloads)} different payloads processed correctly")
    return True


def test_invalid_mac_rejection():
    """Test that tampered data is rejected due to MAC verification failure"""
    print("TEST: Invalid MAC Rejection")

    router = OnionRouter(
        node_id="test-router-3",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    circuit = create_test_circuit()

    original_payload = b"This message will be tampered with"

    # Encrypt the payload
    encrypted = router._onion_encrypt(circuit, original_payload)

    # Tamper with the encrypted data (flip a bit in the ciphertext part)
    # Structure is: nonce(16) + mac(4) + ciphertext
    tampered = bytearray(encrypted)
    tampered[25] ^= 0xFF  # Flip a byte in the ciphertext
    tampered = bytes(tampered)

    # Attempt to decrypt should raise ValueError due to MAC mismatch
    try:
        router._onion_decrypt(circuit, tampered, 0)
        assert False, "Should have raised ValueError for tampered data"
    except ValueError as e:
        assert "Integrity check failed" in str(e)

    print("  ✅ PASS: Tampered data correctly rejected")
    return True


def test_nonce_uniqueness():
    """Test that each encryption uses a different nonce"""
    print("TEST: Nonce Uniqueness")

    router = OnionRouter(
        node_id="test-router-4",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    circuit = create_test_circuit()

    payload = b"Test message for nonce uniqueness"

    # Encrypt the same payload twice
    encrypted1 = router._onion_encrypt(circuit, payload)
    encrypted2 = router._onion_encrypt(circuit, payload)

    # The encrypted outputs should be different (different nonces)
    assert encrypted1 != encrypted2, "Encrypted outputs should differ (different nonces)"

    # But both should decrypt to the same payload
    decrypted1 = encrypted1
    decrypted2 = encrypted2

    for hop_index in range(len(circuit.hops)):
        decrypted1 = router._onion_decrypt(circuit, decrypted1, hop_index)
        decrypted2 = router._onion_decrypt(circuit, decrypted2, hop_index)

    final1 = router._unpad_payload(decrypted1)
    final2 = router._unpad_payload(decrypted2)

    assert final1 == payload, "First decryption should match payload"
    assert final2 == payload, "Second decryption should match payload"

    print("  ✅ PASS: Unique nonces generated for each encryption")
    return True


def test_encrypted_data_too_short():
    """Test that decryption rejects data shorter than minimum size"""
    print("TEST: Encrypted Data Too Short")

    router = OnionRouter(
        node_id="test-router-5",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    circuit = create_test_circuit()

    # Data must be at least 20 bytes (16 nonce + 4 mac)
    too_short = b"short"

    try:
        router._onion_decrypt(circuit, too_short, 0)
        assert False, "Should have raised ValueError for too-short data"
    except ValueError as e:
        assert "Encrypted data too short" in str(e)

    print("  ✅ PASS: Too-short data correctly rejected")
    return True


def test_padding_correctness():
    """Test that padding is applied and removed correctly"""
    print("TEST: Padding Correctness")

    router = OnionRouter(
        node_id="test-router-6",
        node_types={NodeType.GUARD, NodeType.MIDDLE},
        enable_hidden_services=True,
    )

    test_cases = [
        b"A" * 100,
        b"B" * 511,
        b"C" * 512,
        b"D" * 513,
    ]

    for payload in test_cases:
        padded = router._pad_payload(payload)

        # Padded size should be multiple of 512
        assert len(padded) % 512 == 0, f"Padded size should be multiple of 512"

        # Unpadding should recover original
        unpadded = router._unpad_payload(padded)
        assert unpadded == payload, f"Unpadding should recover original"

    print(f"  ✅ PASS: Padding/unpadding works for {len(test_cases)} test cases")
    return True


def main():
    """Run all tests"""
    print("="*60)
    print("VPN Crypto Tests - Nonce Handling Fix Validation")
    print("="*60)
    print()

    tests = [
        test_encrypt_decrypt_round_trip,
        test_multi_hop_circuit,
        test_invalid_mac_rejection,
        test_nonce_uniqueness,
        test_encrypted_data_too_short,
        test_padding_correctness,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ FAIL: Test returned False")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {e}")
            traceback.print_exc()

        print()

    print("="*60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
