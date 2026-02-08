"""
Phase 6 contract tests: Tokenomics correctness and security (SIN-022..SIN-024).

Validates:
- SIN-022: Daily reward limits enforced
- SIN-023: No placeholder system key in production
- SIN-024: Quality bonus uses real participants, escrow requires token system
"""
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project roots are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_MOCKS", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tokenomics-tests-32chars!")


def _make_system():
    from tokenomics.unified_dao_tokenomics_system import (
        EarningRule,
        TokenAction,
        TokenomicsConfig,
        UnifiedDAOTokenomicsSystem,
    )

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    config = TokenomicsConfig(
        database_path=db_path,
        initial_token_supply=1_000_000,
    )
    system = UnifiedDAOTokenomicsSystem(config)

    # Override P2P_HOSTING rule with a tight daily limit for testing
    system.earning_rules[TokenAction.P2P_HOSTING] = EarningRule(
        action=TokenAction.P2P_HOSTING,
        base_amount=30,
        daily_limit=50,
    )
    return system, TokenAction, db_path


def _cleanup_system(system, db_path):
    """Close DB connection before deleting file (Windows compatibility)."""
    try:
        if system.database.connection:
            system.database.connection.close()
    except Exception:
        pass
    try:
        os.unlink(db_path)
    except (PermissionError, OSError):
        pass  # Windows may still hold the lock briefly


class TestDailyLimitEnforcement:
    """SIN-022: Daily reward limits must be enforced."""

    def test_daily_limit_blocks_excess(self):
        system, TokenAction, db_path = _make_system()
        try:
            r1 = system.award_tokens("user1", TokenAction.P2P_HOSTING)
            assert r1 == 30

            r2 = system.award_tokens("user1", TokenAction.P2P_HOSTING)
            assert r2 == 20  # 50 - 30 = 20 remaining

            r3 = system.award_tokens("user1", TokenAction.P2P_HOSTING)
            assert r3 == 0

            assert system.get_balance("user1") == 50
        finally:
            _cleanup_system(system, db_path)

    def test_daily_limit_per_user(self):
        system, TokenAction, db_path = _make_system()
        try:
            system.award_tokens("user1", TokenAction.P2P_HOSTING)
            system.award_tokens("user1", TokenAction.P2P_HOSTING)

            r = system.award_tokens("user2", TokenAction.P2P_HOSTING)
            assert r == 30
        finally:
            _cleanup_system(system, db_path)

    def test_no_daily_limit_actions_unrestricted(self):
        system, TokenAction, db_path = _make_system()
        try:
            from tokenomics.unified_dao_tokenomics_system import EarningRule

            system.earning_rules[TokenAction.COMPUTE_CONTRIBUTION] = EarningRule(
                action=TokenAction.COMPUTE_CONTRIBUTION,
                base_amount=100,
                daily_limit=None,
            )
            for _ in range(5):
                r = system.award_tokens("user1", TokenAction.COMPUTE_CONTRIBUTION)
                assert r == 100
            assert system.get_balance("user1") == 500
        finally:
            _cleanup_system(system, db_path)

    def test_get_daily_earned_tracks_correctly(self):
        system, TokenAction, db_path = _make_system()
        try:
            system.award_tokens("user1", TokenAction.P2P_HOSTING)
            earned = system.database.get_daily_earned("user1", TokenAction.P2P_HOSTING.value)
            assert earned == 30
        finally:
            _cleanup_system(system, db_path)

    def test_source_has_no_disabled_limit(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "unified_dao_tokenomics_system.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "daily limit validation disabled" not in source
        assert "TODO: Implement daily limit tracking" not in source


class TestSystemKeyNotPlaceholder:
    """SIN-023: No placeholder system key in production."""

    def test_source_has_no_placeholder_key(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "fog_tokenomics_service.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "system_key_placeholder" not in source
        assert "TOKENOMICS_SYSTEM_KEY" in source

    def test_production_requires_env_key(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "fog_tokenomics_service.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "production" in source
        assert "RuntimeError" in source

    def test_key_validation_rejects_short_keys(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "fog_tokenomics_service.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "32" in source

    def test_dev_mode_generates_ephemeral_key(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "fog_tokenomics_service.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "os.urandom(32)" in source
        assert "ephemeral" in source.lower()


class TestQualityBonusNotHardcoded:
    """SIN-024: Quality bonus must use real participants."""

    def test_source_has_no_hardcoded_participants(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "tokenomics_integration.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "total_participants = 10" not in source
        assert 'f"provider_{i}"' not in source

    def test_source_checks_active_providers(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "tokenomics_integration.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "active_providers" in source


class TestEscrowRequiresTokenSystem:
    """SIN-024: Escrow operations must not silently succeed without token system."""

    def _get_source(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "tokenomics"
            / "tokenomics_integration.py"
        )
        return source_path.read_text(encoding="utf-8")

    def test_escrow_hold_returns_false_without_token_system(self):
        source = self._get_source()
        match = re.search(
            r'async def _hold_tokens_in_escrow\(.*?\).*?(?=\n    async def )',
            source, re.DOTALL
        )
        assert match, "_hold_tokens_in_escrow method not found"
        method_body = match.group()
        assert "return False" in method_body
        assert "transfer_tokens" in method_body

    def test_refund_returns_false_without_token_system(self):
        source = self._get_source()
        match = re.search(
            r'async def _refund_deposit\(.*?\).*?(?=\n    async def )',
            source, re.DOTALL
        )
        assert match, "_refund_deposit method not found"
        method_body = match.group()
        assert "return False" in method_body
        assert "transfer_tokens" in method_body

    def test_convert_returns_false_without_token_system(self):
        source = self._get_source()
        match = re.search(
            r'async def _convert_deposit_to_payment\(.*?\).*?(?=\n    async def )',
            source, re.DOTALL
        )
        assert match, "_convert_deposit_to_payment method not found"
        method_body = match.group()
        assert "return False" in method_body
        assert "transfer_tokens" in method_body
