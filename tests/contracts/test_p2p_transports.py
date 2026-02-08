"""
Tests for P2P transport hardening (Phase 3).

SIN-009: TRANSPORTS_AVAILABLE reflects reality
SIN-010: TransportCapabilities from local module
SIN-011: Transport interface standardization
SIN-015: Degraded mode surfacing
"""
import os
import sys
from pathlib import Path

# Set TESTING before any backend imports trigger Settings validation
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-contracts-testing-only-32chars")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest


class TestTransportsAvailableTruthful:
    """SIN-009: TRANSPORTS_AVAILABLE must reflect reality."""

    def test_transports_available_is_true_when_modules_exist(self):
        """Real transport modules exist in src/p2p/transports/."""
        from p2p.unified_p2p_system import TRANSPORTS_AVAILABLE

        # The real transport files exist in this project
        assert TRANSPORTS_AVAILABLE is True

    def test_no_stub_classes_in_module(self):
        """No stub/fake transport classes should be defined in unified module."""
        import p2p.unified_p2p_system as mod

        source = Path(mod.__file__).read_text()
        # Should not contain stub class definitions
        assert 'class HtxClient:' not in source
        assert 'class TransportManager:' not in source
        assert '"""Stub' not in source

    def test_imports_from_local_transports(self):
        """Imports should come from .transports, not ...infrastructure."""
        import p2p.unified_p2p_system as mod

        source = Path(mod.__file__).read_text()
        # Should NOT import from nonexistent infrastructure path
        assert 'from ...infrastructure.p2p' not in source
        # Should import from local transports
        assert 'from .transports' in source


class TestTransportCapabilitiesLocal:
    """SIN-010: TransportCapabilities from local module, not broken import."""

    def test_transport_capabilities_importable(self):
        """TransportCapabilities should import from local transports."""
        from p2p.transports.base_transport import TransportCapabilities

        caps = TransportCapabilities()
        assert caps.supports_unicast is True
        assert caps.max_message_size == 65536
        assert hasattr(caps, 'is_offline_capable')
        assert hasattr(caps, 'provides_encryption')

    def test_get_transport_capabilities_no_broken_import(self):
        """_get_transport_capabilities must not import from infrastructure."""
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        system = UnifiedDecentralizedSystem(
            node_id="test-node-001",
            enable_bitchat=False,
            enable_betanet=False,
        )

        from p2p.unified_p2p_system import DecentralizedTransportType

        # Should not raise ImportError
        caps = system._get_transport_capabilities(DecentralizedTransportType.BITCHAT_BLE)
        assert caps is not None
        assert caps.is_offline_capable is True
        assert caps.requires_internet is False

        caps_betanet = system._get_transport_capabilities(DecentralizedTransportType.BETANET_HTX)
        assert caps_betanet is not None
        assert caps_betanet.requires_internet is True
        assert caps_betanet.provides_encryption is True


class TestTransportInterfaceStandard:
    """SIN-011: Real transports implement standard interface."""

    def test_betanet_transport_has_send(self):
        """BetaNetTransport must have async send() method."""
        from p2p.transports.betanet_transport import BetaNetTransport
        import inspect

        assert hasattr(BetaNetTransport, 'send')
        assert inspect.iscoroutinefunction(BetaNetTransport.send)

    def test_bitchat_transport_has_send(self):
        """BitChatTransport must have async send() method."""
        from p2p.transports.bitchat_transport import BitChatTransport
        import inspect

        assert hasattr(BitChatTransport, 'send')
        assert inspect.iscoroutinefunction(BitChatTransport.send)

    def test_both_transports_have_get_capabilities(self):
        """Both transports must implement get_capabilities()."""
        from p2p.transports.betanet_transport import BetaNetTransport
        from p2p.transports.bitchat_transport import BitChatTransport
        from p2p.transports.base_transport import TransportCapabilities

        betanet = BetaNetTransport(node_id="test-001")
        caps = betanet.get_capabilities()
        assert isinstance(caps, TransportCapabilities)

        bitchat = BitChatTransport(node_id="test-002")
        caps = bitchat.get_capabilities()
        assert isinstance(caps, TransportCapabilities)

    def test_unified_system_uses_send_not_send_message(self):
        """_send_via_direct_transport should call send(), not send_message()."""
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        import inspect
        source = inspect.getsource(UnifiedDecentralizedSystem._send_via_direct_transport)
        # Should use transport.send()
        assert 'hasattr(selected_transport, "send")' in source
        # Should NOT reference send_message
        assert 'send_message' not in source


class TestMessageHandlersDictFormat:
    """SIN-011: Message handlers accept dict format from real transports."""

    @pytest.mark.asyncio
    async def test_bitchat_handler_accepts_dict(self):
        """_handle_bitchat_message should accept dict, not unified_message object."""
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        system = UnifiedDecentralizedSystem(
            node_id="test-node-001",
            enable_bitchat=False,
            enable_betanet=False,
        )

        # Should not raise when given a dict (real transport format)
        msg_dict = {
            "message_id": "msg-001",
            "sender_id": "peer-001",
            "receiver_id": "test-node-001",
            "payload": b"hello".hex(),
            "message_type": "data",
        }
        await system._handle_bitchat_message(msg_dict)
        assert system.metrics["bitchat_messages"] == 1

    @pytest.mark.asyncio
    async def test_betanet_handler_accepts_dict(self):
        """_handle_betanet_message should accept dict, not unified_message object."""
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        system = UnifiedDecentralizedSystem(
            node_id="test-node-002",
            enable_bitchat=False,
            enable_betanet=False,
        )

        msg_dict = {
            "message_id": "msg-002",
            "sender_id": "peer-002",
            "receiver_id": "test-node-002",
            "payload": b"secret".hex(),
            "message_type": "data",
        }
        await system._handle_betanet_message(msg_dict)
        assert system.metrics["betanet_messages"] == 1


class TestDegradedModeSurfacing:
    """SIN-015: Degraded mode properly reported."""

    def test_status_includes_degraded_flag(self):
        """get_status() must include degraded flag."""
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        system = UnifiedDecentralizedSystem(
            node_id="test-node-001",
            enable_bitchat=False,
            enable_betanet=False,
        )
        status = system.get_status()
        assert "degraded" in status
        assert "transports_available" in status

    def test_health_reports_degraded_when_no_transports(self):
        """get_health() should report degraded when no transports active."""
        from p2p.unified_p2p_system import UnifiedDecentralizedSystem

        system = UnifiedDecentralizedSystem(
            node_id="test-node-001",
            enable_bitchat=False,
            enable_betanet=False,
        )
        # Not started, no transports
        health = system.get_health()
        assert health["status"] in ("unhealthy", "degraded")
        assert "degraded" in health

    def test_service_status_has_degraded_enum(self):
        """ServiceStatus must include DEGRADED value."""
        from backend.server.services.registry import ServiceStatus

        assert hasattr(ServiceStatus, "DEGRADED")
        assert ServiceStatus.DEGRADED.value == "degraded"
