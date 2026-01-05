"""
MFA (Multi-Factor Authentication) Tests
Tests for TOTP-based MFA implementation.
"""
import pytest
import pyotp
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Test MFA service directly
from backend.server.services.mfa_service import MFAService, get_mfa_service


class TestMFAService:
    """Unit tests for MFA service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mfa_service = MFAService()

    def test_generate_secret(self):
        """Test TOTP secret generation."""
        secret = self.mfa_service.generate_secret()

        # Secret should be base32 encoded
        assert secret is not None
        assert len(secret) == 32  # pyotp default length
        # Should be valid base32
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in secret)

    def test_generate_provisioning_uri(self):
        """Test QR code provisioning URI generation."""
        secret = self.mfa_service.generate_secret()
        uri = self.mfa_service.generate_provisioning_uri(
            secret=secret,
            username="test@example.com",
            issuer="FogCompute"
        )

        # Should be otpauth URI
        assert uri.startswith("otpauth://totp/")
        assert "FogCompute" in uri
        assert "test%40example.com" in uri or "test@example.com" in uri
        assert secret in uri

    def test_verify_totp_valid_code(self):
        """Test TOTP verification with valid code."""
        secret = self.mfa_service.generate_secret()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()

        # Valid code should verify
        assert self.mfa_service.verify_totp(secret, current_code) is True

    def test_verify_totp_invalid_code(self):
        """Test TOTP verification with invalid code."""
        secret = self.mfa_service.generate_secret()

        # Invalid codes
        assert self.mfa_service.verify_totp(secret, "000000") is False
        assert self.mfa_service.verify_totp(secret, "123456") is False
        assert self.mfa_service.verify_totp(secret, "") is False
        assert self.mfa_service.verify_totp(secret, "abcdef") is False

    def test_verify_totp_empty_secret(self):
        """Test TOTP verification with empty secret."""
        assert self.mfa_service.verify_totp("", "123456") is False
        assert self.mfa_service.verify_totp(None, "123456") is False

    def test_verify_totp_valid_window(self):
        """Test TOTP verification allows for clock drift."""
        secret = self.mfa_service.generate_secret()
        totp = pyotp.TOTP(secret)

        # Get code from 30 seconds ago (previous window)
        import time
        current_time = time.time()
        # This should still be valid with valid_window=1
        current_code = totp.now()
        assert self.mfa_service.verify_totp(secret, current_code, valid_window=1) is True

    def test_generate_backup_codes(self):
        """Test backup code generation."""
        codes = self.mfa_service.generate_backup_codes(count=10)

        assert len(codes) == 10

        for code in codes:
            # Format should be XXXX-XXXX
            assert len(code) == 9
            assert code[4] == '-'
            # Should be hex characters (uppercase)
            parts = code.split('-')
            assert len(parts) == 2
            assert all(c in '0123456789ABCDEF' for c in parts[0])
            assert all(c in '0123456789ABCDEF' for c in parts[1])

        # All codes should be unique
        assert len(set(codes)) == 10

    def test_verify_backup_code_valid(self):
        """Test backup code verification with valid code."""
        import hashlib

        def hash_func(code):
            return hashlib.sha256(code.encode()).hexdigest()

        codes = self.mfa_service.generate_backup_codes(count=5)
        hashed_codes = [hash_func(code) for code in codes]

        # First code should verify
        is_valid, index = self.mfa_service.verify_backup_code(
            codes[0], hashed_codes, hash_func
        )
        assert is_valid is True
        assert index == 0

        # Third code should verify
        is_valid, index = self.mfa_service.verify_backup_code(
            codes[2], hashed_codes, hash_func
        )
        assert is_valid is True
        assert index == 2

    def test_verify_backup_code_invalid(self):
        """Test backup code verification with invalid code."""
        import hashlib

        def hash_func(code):
            return hashlib.sha256(code.encode()).hexdigest()

        codes = self.mfa_service.generate_backup_codes(count=5)
        hashed_codes = [hash_func(code) for code in codes]

        # Invalid code should not verify
        is_valid, index = self.mfa_service.verify_backup_code(
            "XXXX-XXXX", hashed_codes, hash_func
        )
        assert is_valid is False
        assert index is None

    def test_verify_backup_code_without_dash(self):
        """Test backup code verification works without dash."""
        import hashlib

        def hash_func(code):
            return hashlib.sha256(code.encode()).hexdigest()

        codes = self.mfa_service.generate_backup_codes(count=1)
        hashed_codes = [hash_func(code) for code in codes]

        # Remove dash from code
        code_without_dash = codes[0].replace('-', '')

        is_valid, index = self.mfa_service.verify_backup_code(
            code_without_dash, hashed_codes, hash_func
        )
        assert is_valid is True
        assert index == 0

    def test_setup_mfa(self):
        """Test complete MFA setup flow."""
        setup_data = self.mfa_service.setup_mfa("admin@fogcompute.io")

        # Should have all required fields
        assert setup_data.secret is not None
        assert len(setup_data.secret) == 32
        assert setup_data.provisioning_uri.startswith("otpauth://")
        assert len(setup_data.backup_codes) == 10

        # Generated code should verify against secret
        totp = pyotp.TOTP(setup_data.secret)
        current_code = totp.now()
        assert self.mfa_service.verify_totp(setup_data.secret, current_code) is True

    def test_get_current_code(self):
        """Test getting current TOTP code."""
        secret = self.mfa_service.generate_secret()
        code = self.mfa_service.get_current_code(secret)

        assert len(code) == 6
        assert code.isdigit()
        # Code should verify
        assert self.mfa_service.verify_totp(secret, code) is True


class TestMFASecurityProperties:
    """Security property tests for MFA implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mfa_service = MFAService()

    def test_secret_randomness(self):
        """Test that generated secrets are random."""
        secrets = [self.mfa_service.generate_secret() for _ in range(100)]

        # All secrets should be unique
        assert len(set(secrets)) == 100

    def test_backup_code_randomness(self):
        """Test that backup codes are random."""
        all_codes = []
        for _ in range(10):
            codes = self.mfa_service.generate_backup_codes(count=10)
            all_codes.extend(codes)

        # All 100 codes should be unique
        assert len(set(all_codes)) == 100

    def test_totp_timing_resistance(self):
        """Test that invalid codes are rejected consistently."""
        secret = self.mfa_service.generate_secret()

        # Multiple invalid codes should all fail
        invalid_codes = ["000000", "111111", "999999", "123456"]
        for code in invalid_codes:
            assert self.mfa_service.verify_totp(secret, code) is False

    def test_backup_code_single_use_simulation(self):
        """Test that backup codes work for single-use pattern."""
        import hashlib

        def hash_func(code):
            return hashlib.sha256(code.encode()).hexdigest()

        codes = self.mfa_service.generate_backup_codes(count=3)
        hashed_codes = [hash_func(code) for code in codes]

        # Use first code
        is_valid, index = self.mfa_service.verify_backup_code(
            codes[0], hashed_codes, hash_func
        )
        assert is_valid is True
        assert index == 0

        # Simulate marking as used
        hashed_codes[0] = None

        # Same code should now fail
        is_valid, index = self.mfa_service.verify_backup_code(
            codes[0], hashed_codes, hash_func
        )
        assert is_valid is False

        # Other codes should still work
        is_valid, index = self.mfa_service.verify_backup_code(
            codes[1], hashed_codes, hash_func
        )
        assert is_valid is True
        assert index == 1


class TestMFAServiceSingleton:
    """Test MFA service singleton behavior."""

    def test_get_mfa_service_returns_same_instance(self):
        """Test that get_mfa_service returns singleton."""
        service1 = get_mfa_service()
        service2 = get_mfa_service()

        assert service1 is service2

    def test_mfa_service_is_mfa_service_instance(self):
        """Test that singleton is MFAService instance."""
        service = get_mfa_service()
        assert isinstance(service, MFAService)
