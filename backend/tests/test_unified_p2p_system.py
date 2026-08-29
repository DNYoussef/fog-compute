"""Regression tests for unified P2P lifecycle and message contracts."""
import json

import pytest

from p2p import unified_p2p_system as p2p_module


class FakeTransport:
    """Minimal transport double for unified P2P tests."""

    def __init__(self, *, start_result=True, available=True, connected=True):
        self.start_result = start_result
        self.available = available
        self.connected = connected
        self.started = False
        self.start_calls = 0
        self.stop_calls = 0
        self.handlers = []
        self.sent_messages = []

    def register_message_handler(self, handler):
        self.handlers.append(handler)

    async def start(self):
        self.start_calls += 1
        self.started = self.start_result
        return self.start_result

    async def stop(self):
        self.stop_calls += 1
        self.started = False
        return True

    def is_available(self):
        return self.started and self.available

    def is_connected(self):
        return self.started and self.connected

    async def send(self, message):
        self.sent_messages.append(message)
        return True


def _patch_bitchat_transport(monkeypatch, transport):
    monkeypatch.setattr(p2p_module, "TRANSPORTS_AVAILABLE", True)
    monkeypatch.setattr(p2p_module, "BitChatBLETransport", lambda **kwargs: transport)


@pytest.mark.asyncio
async def test_start_starts_transport_before_background_tasks(monkeypatch):
    """System start must only launch background tasks after it marks itself running."""
    transport = FakeTransport()
    _patch_bitchat_transport(monkeypatch, transport)

    system = p2p_module.UnifiedDecentralizedSystem(
        node_id="node-1",
        enable_bitchat=True,
        enable_betanet=False,
    )
    observed_running = []
    monkeypatch.setattr(
        system,
        "_start_background_tasks",
        lambda: observed_running.append(system._running),
    )

    started = await system.start()

    assert started is True
    assert transport.start_calls == 1
    assert observed_running == [True]
    assert p2p_module.DecentralizedTransportType.BITCHAT_BLE in system.transports

    await system.stop()


@pytest.mark.asyncio
async def test_start_fails_when_transport_does_not_report_running(monkeypatch):
    """Startup must fail if the selected transport never becomes available/connected."""
    transport = FakeTransport(start_result=True, available=False, connected=False)
    _patch_bitchat_transport(monkeypatch, transport)

    system = p2p_module.UnifiedDecentralizedSystem(
        node_id="node-2",
        enable_bitchat=True,
        enable_betanet=False,
    )
    monkeypatch.setattr(system, "_start_background_tasks", lambda: None)

    started = await system.start()

    assert started is False
    assert transport.start_calls == 1
    assert transport.stop_calls == 1
    assert system._running is False
    assert system.transports == {}


@pytest.mark.asyncio
async def test_send_message_uses_canonical_top_level_message_id(monkeypatch):
    """Send path must populate the canonical top-level message ID expected by receivers."""
    transport = FakeTransport()
    system = p2p_module.UnifiedDecentralizedSystem(
        node_id="node-3",
        enable_bitchat=False,
        enable_betanet=False,
    )
    system._running = True
    system.transports[p2p_module.DecentralizedTransportType.BITCHAT_BLE] = transport

    sent = await system.send_message(
        receiver_id="peer-1",
        message_type="data",
        payload=b"hello",
    )

    assert sent is True
    assert len(transport.sent_messages) == 1
    sent_message = transport.sent_messages[0]
    assert "message_id" in sent_message
    assert sent_message["message_id"] in system.pending_acks
    assert sent_message["metadata"]["message_id"] == sent_message["message_id"]
    assert sent_message["requires_ack"] is True


@pytest.mark.asyncio
async def test_ack_message_clears_pending_ack(monkeypatch):
    """Received ACKs must clear the pending-ack entry for the original message."""
    transport = FakeTransport()
    system = p2p_module.UnifiedDecentralizedSystem(
        node_id="node-4",
        enable_bitchat=False,
        enable_betanet=False,
    )
    system._running = True
    system.transports[p2p_module.DecentralizedTransportType.BITCHAT_BLE] = transport

    await system.send_message(
        receiver_id="peer-2",
        message_type="data",
        payload=b"payload",
    )
    original_message_id = next(iter(system.pending_acks))

    await system._handle_bitchat_message(
        {
            "message_id": "ack-1",
            "sender_id": "peer-2",
            "receiver_id": "node-4",
            "message_type": "ack",
            "payload": json.dumps({"original_message_id": original_message_id}).encode("utf-8"),
        }
    )

    assert original_message_id not in system.pending_acks


@pytest.mark.asyncio
async def test_duplicate_messages_are_only_delivered_once(monkeypatch):
    """Duplicate delivery must be dropped before handlers run a second time."""
    system = p2p_module.UnifiedDecentralizedSystem(
        node_id="node-5",
        enable_bitchat=False,
        enable_betanet=False,
    )
    delivered = []
    system.register_message_handler(lambda message, transport: delivered.append(message.message_id))

    duplicate_message = {
        "message_id": "dup-1",
        "sender_id": "peer-3",
        "receiver_id": "node-5",
        "message_type": "data",
        "payload": b"hello",
        "requires_ack": False,
    }

    await system._handle_bitchat_message(duplicate_message)
    await system._handle_bitchat_message(duplicate_message)

    assert delivered == ["dup-1"]
