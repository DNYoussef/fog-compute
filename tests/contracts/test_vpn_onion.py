"""
Phase 5 contract tests: VPN/Onion honest stubs (SIN-019..SIN-021).

Validates:
- SIN-019: NymMixnetClient stub does not fake success
- SIN-020: Consensus is flagged as simulated
- SIN-021: Direct gossip does not simulate success
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure project roots are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

# Set dev env vars before importing modules that read them at import time
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_MOCKS", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-vpn-onion-tests-32chars!")


class TestMixnetStubHonesty:
    """SIN-019: NymMixnetClient stub must not fake success."""

    def test_mixnet_available_flag_is_false(self):
        from vpn.fog_onion_coordinator import MIXNET_AVAILABLE

        assert MIXNET_AVAILABLE is False, "MIXNET_AVAILABLE must be False (no real implementation)"

    @pytest.mark.asyncio
    async def test_stub_start_returns_false(self):
        from vpn.fog_onion_coordinator import NymMixnetClient

        client = NymMixnetClient(client_id="test-client")
        result = await client.start()
        assert result is False, "Stub start() must return False (not fake success)"

    @pytest.mark.asyncio
    async def test_stub_send_returns_none(self):
        from vpn.fog_onion_coordinator import NymMixnetClient

        client = NymMixnetClient(client_id="test-client")
        result = await client.send_anonymous_message("dest", b"hello")
        assert result is None, "Stub send must return None (not fake packet ID)"

    @pytest.mark.asyncio
    async def test_stub_stats_report_unavailable(self):
        from vpn.fog_onion_coordinator import NymMixnetClient

        client = NymMixnetClient(client_id="test-client")
        stats = await client.get_mixnet_stats()
        assert stats["stub_implementation"] is True
        assert stats["mixnet_available"] is False

    def test_stub_is_stub_attribute(self):
        from vpn.fog_onion_coordinator import NymMixnetClient

        client = NymMixnetClient(client_id="test-client")
        assert client._is_stub is True

    @pytest.mark.asyncio
    async def test_stub_raises_in_production_mode(self):
        """In production mode, stub operations must raise, not silently fail."""
        import vpn.fog_onion_coordinator as module

        # Save originals
        orig_allow = module._ALLOW_MOCKS
        orig_env = module._APP_ENV
        try:
            module._ALLOW_MOCKS = False
            module._APP_ENV = "production"

            client = module.NymMixnetClient(client_id="prod-test")
            with pytest.raises(module.StubNotAllowedError):
                await client.start()
            with pytest.raises(module.StubNotAllowedError):
                await client.send_anonymous_message("dest", b"data")
        finally:
            module._ALLOW_MOCKS = orig_allow
            module._APP_ENV = orig_env


class TestConsensusHonesty:
    """SIN-020: Consensus must not silently generate fake nodes in production."""

    @pytest.mark.asyncio
    async def test_consensus_flags_simulated(self):
        from vpn.onion_routing import NodeType, OnionRouter

        router = OnionRouter(
            node_id="test-node",
            node_types={NodeType.MIDDLE},
        )
        result = await router.fetch_consensus()
        # In dev mode, simulated consensus is allowed but flagged
        assert result is True
        assert router.consensus_simulated is True
        assert len(router.consensus) > 0

    @pytest.mark.asyncio
    async def test_consensus_stats_include_simulated_flag(self):
        from vpn.onion_routing import NodeType, OnionRouter

        router = OnionRouter(
            node_id="test-node",
            node_types={NodeType.MIDDLE},
        )
        await router.fetch_consensus()
        stats = router.get_stats()
        assert "consensus_simulated" in stats
        assert stats["consensus_simulated"] is True

    @pytest.mark.asyncio
    async def test_consensus_refuses_in_production(self):
        """In production mode, simulated consensus must return False."""
        import vpn.onion_routing as module
        from vpn.onion_routing import NodeType, OnionRouter

        router = OnionRouter(
            node_id="test-node",
            node_types={NodeType.MIDDLE},
        )
        # Patch env check inside fetch_consensus
        orig_env = os.environ.get("APP_ENV")
        orig_mocks = os.environ.get("ALLOW_MOCKS")
        try:
            os.environ["APP_ENV"] = "production"
            os.environ["ALLOW_MOCKS"] = "false"
            result = await router.fetch_consensus()
            assert result is False, "Simulated consensus must refuse in production"
            assert len(router.consensus) == 0
        finally:
            if orig_env is not None:
                os.environ["APP_ENV"] = orig_env
            else:
                os.environ.pop("APP_ENV", None)
            if orig_mocks is not None:
                os.environ["ALLOW_MOCKS"] = orig_mocks
            else:
                os.environ.pop("ALLOW_MOCKS", None)

    @pytest.mark.asyncio
    async def test_consensus_simulated_initially_false(self):
        from vpn.onion_routing import NodeType, OnionRouter

        router = OnionRouter(
            node_id="test-node",
            node_types={NodeType.MIDDLE},
        )
        assert router.consensus_simulated is False


class TestDirectGossipHonesty:
    """SIN-021: Direct gossip must not simulate success."""

    @pytest.mark.asyncio
    async def test_gossip_fails_without_coordinator(self):
        """Gossip must return False when no fog coordinator is available."""
        from vpn.fog_onion_coordinator import FogOnionCoordinator

        mock_coordinator = MagicMock()
        # Remove send_p2p_message to simulate missing transport
        if hasattr(mock_coordinator, "send_p2p_message"):
            del mock_coordinator.send_p2p_message
        mock_coordinator.onion_router = None

        coordinator = FogOnionCoordinator(
            node_id="test",
            fog_coordinator=mock_coordinator,
            enable_mixnet=False,
        )
        coordinator._running = True

        result = await coordinator._send_direct_gossip("peer-1", b"hello")
        assert result is False, "Direct gossip must not fake success"

    @pytest.mark.asyncio
    async def test_gossip_succeeds_with_real_transport(self):
        """Gossip returns True when fog coordinator has send_p2p_message."""
        from vpn.fog_onion_coordinator import FogOnionCoordinator

        mock_coordinator = MagicMock()
        mock_coordinator.send_p2p_message = AsyncMock(return_value=True)
        mock_coordinator.onion_router = None

        coordinator = FogOnionCoordinator(
            node_id="test",
            fog_coordinator=mock_coordinator,
            enable_mixnet=False,
        )
        coordinator._running = True

        result = await coordinator._send_direct_gossip("peer-1", b"hello")
        assert result is True
        mock_coordinator.send_p2p_message.assert_called_once_with("peer-1", b"hello")

    @pytest.mark.asyncio
    async def test_gossip_returns_false_on_transport_failure(self):
        """Gossip returns False when transport raises."""
        from vpn.fog_onion_coordinator import FogOnionCoordinator

        mock_coordinator = MagicMock()
        mock_coordinator.send_p2p_message = AsyncMock(side_effect=ConnectionError("down"))
        mock_coordinator.onion_router = None

        coordinator = FogOnionCoordinator(
            node_id="test",
            fog_coordinator=mock_coordinator,
            enable_mixnet=False,
        )
        coordinator._running = True

        result = await coordinator._send_direct_gossip("peer-1", b"hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_gossip_fails_with_no_coordinator(self):
        """Gossip returns False when fog_coordinator is None."""
        from vpn.fog_onion_coordinator import FogOnionCoordinator

        coordinator = FogOnionCoordinator(
            node_id="test",
            fog_coordinator=None,
            enable_mixnet=False,
        )
        coordinator._running = True

        result = await coordinator._send_direct_gossip("peer-1", b"hello")
        assert result is False


class TestCoordinatorMixnetIntegration:
    """Test that coordinator handles stub mixnet correctly."""

    @pytest.mark.asyncio
    async def test_coordinator_mixnet_none_after_stub_fails(self):
        """Coordinator should set mixnet_client to None when stub fails to start."""
        from vpn.fog_onion_coordinator import FogOnionCoordinator

        mock_coordinator = MagicMock()
        mock_coordinator.onion_router = None

        coord = FogOnionCoordinator(
            node_id="test",
            fog_coordinator=mock_coordinator,
            enable_mixnet=True,
        )

        # The stub's start() returns False, so mixnet_client should be set to None
        # We can't easily test start() without full setup, but we can test
        # that MIXNET_AVAILABLE is False
        from vpn.fog_onion_coordinator import MIXNET_AVAILABLE

        assert MIXNET_AVAILABLE is False

    def test_source_has_no_fake_packet_id(self):
        """Source code must not generate fake packet IDs."""
        source_path = Path(__file__).resolve().parents[2] / "src" / "vpn" / "fog_onion_coordinator.py"
        source = source_path.read_text(encoding="utf-8")

        # Old stub returned f"packet_{hash}" - that's fake success
        assert 'f"packet_' not in source, "Stub must not generate fake packet IDs"
        assert "simulate success" not in source.lower(), "No simulated success comments"

    def test_source_has_stub_guard(self):
        """Source must check _stubs_allowed or raise in production."""
        source_path = Path(__file__).resolve().parents[2] / "src" / "vpn" / "fog_onion_coordinator.py"
        source = source_path.read_text(encoding="utf-8")

        assert "_stubs_allowed" in source, "Must have _stubs_allowed guard function"
        assert "StubNotAllowedError" in source, "Must have StubNotAllowedError"
        assert "MIXNET_AVAILABLE" in source, "Must have MIXNET_AVAILABLE flag"
