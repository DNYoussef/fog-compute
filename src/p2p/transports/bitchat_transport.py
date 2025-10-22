#!/usr/bin/env python3
"""
BitChat Transport Module
Integrates BitChat BLE mesh as a transport for P2P Unified System

ARCHITECTURE:
- BitChat operates as BLE mesh transport (one of several transports)
- P2P Unified System coordinates protocol selection
- This module bridges between BitChat backend service and P2P

INTEGRATION POINTS:
- BitChat Backend Service (backend/server/services/bitchat.py)
- BitChat API Routes (backend/server/routes/bitchat.py)
- P2P Unified System (src/p2p/unified_p2p_system.py)
"""

import asyncio
import aiohttp
import json
import logging
import time
from typing import Any, Optional

from .base_transport import BaseTransport, TransportType, TransportCapabilities

logger = logging.getLogger(__name__)


class BitChatTransport(BaseTransport):
    """
    BitChat BLE Mesh Transport.

    Integrates BitChat backend service as a transport module for
    the P2P Unified System. Provides BLE mesh messaging through
    the BitChat REST API and WebSocket connection.

    Features:
    - BLE mesh multi-hop routing (7 hops)
    - Offline-capable store-and-forward
    - WebSocket real-time message delivery
    - Integration with BitChat backend service
    """

    def __init__(
        self,
        node_id: str,
        bitchat_api_url: str = "http://localhost:8000",
        display_name: Optional[str] = None,
        public_key: Optional[str] = None,
        max_message_size: int = 65536,
        enable_websocket: bool = True,
    ):
        super().__init__(TransportType.BLE_MESH, node_id)

        self.bitchat_api_url = bitchat_api_url.rstrip("/")
        self.display_name = display_name or f"Node-{node_id[:8]}"
        self.public_key = public_key or self._generate_dummy_public_key()
        self.max_message_size = max_message_size
        self.enable_websocket = enable_websocket

        # HTTP session for REST API
        self.session: Optional[aiohttp.ClientSession] = None

        # WebSocket for real-time messages
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.ws_task: Optional[asyncio.Task] = None

        # Peer tracking
        self.known_peers: dict[str, dict] = {}
        self.peer_count = 0

        logger.info(f"BitChat transport initialized for {node_id}")

    def _generate_dummy_public_key(self) -> str:
        """Generate dummy public key for testing."""
        import secrets
        return secrets.token_hex(32)

    async def start(self) -> bool:
        """Start BitChat transport."""
        if self._running:
            logger.warning("BitChat transport already running")
            return True

        try:
            # Create HTTP session
            self.session = aiohttp.ClientSession()

            # Register with BitChat backend
            success = await self._register_peer()
            if not success:
                logger.error("Failed to register with BitChat backend")
                await self.stop()
                return False

            # Start WebSocket connection for real-time messages
            if self.enable_websocket:
                self.ws_task = asyncio.create_task(self._websocket_loop())

            # Discover peers
            await self._discover_peers()

            self._running = True
            logger.info("BitChat transport started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start BitChat transport: {e}")
            self.errors.append(f"Start failed: {str(e)}")
            await self.stop()
            return False

    async def stop(self) -> bool:
        """Stop BitChat transport."""
        if not self._running:
            return True

        self._running = False

        try:
            # Stop WebSocket
            if self.ws_task and not self.ws_task.done():
                self.ws_task.cancel()
                try:
                    await self.ws_task
                except asyncio.CancelledError:
                    pass

            if self.ws and not self.ws.closed:
                await self.ws.close()

            # Update peer status to offline
            await self._update_peer_status(False)

            # Close HTTP session
            if self.session and not self.session.closed:
                await self.session.close()

            logger.info("BitChat transport stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping BitChat transport: {e}")
            return False

    async def send(self, message: dict[str, Any]) -> bool:
        """
        Send message through BitChat.

        Args:
            message: P2P message dictionary with:
                - sender_id: str
                - receiver_id: str
                - payload: bytes
                - message_type: str
                - priority: int

        Returns:
            True if sent successfully
        """
        if not self._running or not self.session:
            logger.error("BitChat transport not running")
            return False

        try:
            # Convert P2P message to BitChat format
            bitchat_message = {
                "from_peer_id": message.get("sender_id", self.node_id),
                "to_peer_id": message.get("receiver_id"),
                "content": message.get("payload", b"").hex() if isinstance(message.get("payload"), bytes) else str(message.get("payload", "")),
                "encryption_algorithm": "AES-256-GCM",
                "ttl": 3600,  # 1 hour TTL
            }

            # Send via BitChat API
            url = f"{self.bitchat_api_url}/api/bitchat/messages/send"
            async with self.session.post(url, json=bitchat_message) as resp:
                if resp.status == 201:
                    self.messages_sent += 1
                    self.last_activity = time.time()
                    logger.debug(f"Message sent via BitChat to {bitchat_message['to_peer_id']}")
                    return True
                else:
                    error_text = await resp.text()
                    logger.error(f"BitChat send failed ({resp.status}): {error_text}")
                    self.errors.append(f"Send failed: {resp.status}")
                    return False

        except Exception as e:
            logger.error(f"Error sending message via BitChat: {e}")
            self.errors.append(f"Send error: {str(e)}")
            return False

    async def receive(self) -> Optional[dict[str, Any]]:
        """
        Receive message from BitChat.

        BitChat uses WebSocket for real-time delivery, so this
        method returns None. Messages are delivered via handlers.

        Returns:
            None (messages delivered via WebSocket handlers)
        """
        # BitChat uses WebSocket push model, not polling
        return None

    def get_capabilities(self) -> TransportCapabilities:
        """Get BitChat transport capabilities."""
        return TransportCapabilities(
            supports_unicast=True,
            supports_broadcast=True,
            supports_multicast=True,
            max_message_size=self.max_message_size,
            typical_latency_ms=2000.0,  # BLE mesh is slower
            bandwidth_mbps=0.1,  # BLE bandwidth
            is_offline_capable=True,  # Store-and-forward
            requires_internet=False,  # BLE mesh works offline
            works_on_cellular=False,  # BLE only
            works_on_wifi=True,  # Can use WiFi-BLE bridge
            provides_encryption=True,  # End-to-end encryption
            supports_forward_secrecy=False,
            anonymity_level=1,  # Basic privacy
            battery_impact="medium",  # BLE is battery intensive
            data_cost_impact="low",  # No internet data
            is_available=self.is_available(),
            is_connected=self.is_connected(),
            connection_quality=1.0 if self.is_connected() else 0.0,
            supports_store_and_forward=True,
            supports_multi_hop=True,
            max_hops=7,  # BitChat default
        )

    def is_available(self) -> bool:
        """Check if BitChat transport is available."""
        return self._running and self.session is not None and not self.session.closed

    def is_connected(self) -> bool:
        """Check if connected to BitChat backend."""
        return (
            self._running
            and self.session is not None
            and not self.session.closed
            and (self.ws is None or not self.ws.closed)
        )

    def get_status(self) -> dict[str, Any]:
        """Get BitChat transport status."""
        status = super().get_status()
        status.update({
            "bitchat_api_url": self.bitchat_api_url,
            "display_name": self.display_name,
            "peer_count": self.peer_count,
            "websocket_connected": self.ws is not None and not self.ws.closed,
            "known_peers": len(self.known_peers),
        })
        return status

    # ============================================================================
    # BitChat Backend Integration
    # ============================================================================

    async def _register_peer(self) -> bool:
        """Register this node as a BitChat peer."""
        try:
            url = f"{self.bitchat_api_url}/api/bitchat/peers/register"
            data = {
                "peer_id": self.node_id,
                "public_key": self.public_key,
                "display_name": self.display_name,
            }

            async with self.session.post(url, json=data) as resp:
                if resp.status == 201:
                    logger.info(f"Registered with BitChat as {self.node_id}")
                    return True
                else:
                    error_text = await resp.text()
                    logger.error(f"BitChat registration failed ({resp.status}): {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error registering with BitChat: {e}")
            return False

    async def _update_peer_status(self, is_online: bool) -> bool:
        """Update peer online status."""
        try:
            url = f"{self.bitchat_api_url}/api/bitchat/peers/{self.node_id}/status"
            params = {"is_online": is_online}

            async with self.session.put(url, params=params) as resp:
                if resp.status == 200:
                    logger.debug(f"Updated BitChat status to {'online' if is_online else 'offline'}")
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f"Error updating peer status: {e}")
            return False

    async def _discover_peers(self) -> list[dict]:
        """Discover peers from BitChat backend."""
        try:
            url = f"{self.bitchat_api_url}/api/bitchat/peers"
            params = {"online_only": True}

            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    peers = await resp.json()
                    self.peer_count = len(peers)

                    # Update known peers
                    for peer in peers:
                        self.known_peers[peer["peer_id"]] = peer

                    logger.info(f"Discovered {len(peers)} BitChat peers")
                    return peers
                else:
                    return []

        except Exception as e:
            logger.error(f"Error discovering peers: {e}")
            return []

    async def _websocket_loop(self):
        """WebSocket connection loop for real-time messages."""
        while self._running:
            try:
                # Connect to BitChat WebSocket
                ws_url = f"{self.bitchat_api_url.replace('http', 'ws')}/api/bitchat/ws/{self.node_id}"

                async with self.session.ws_connect(ws_url) as ws:
                    self.ws = ws
                    logger.info(f"BitChat WebSocket connected: {ws_url}")

                    # Send periodic pings
                    last_ping = time.time()

                    async for msg in ws:
                        if not self._running:
                            break

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_websocket_message(msg.data)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"BitChat WebSocket error: {ws.exception()}")
                            break

                        # Send ping every 30 seconds
                        if time.time() - last_ping > 30:
                            await ws.send_json({"type": "ping"})
                            last_ping = time.time()

            except asyncio.CancelledError:
                logger.info("BitChat WebSocket loop cancelled")
                break

            except Exception as e:
                logger.error(f"BitChat WebSocket error: {e}")
                self.errors.append(f"WebSocket error: {str(e)}")

                if self._running:
                    # Reconnect after delay
                    await asyncio.sleep(5)
                else:
                    break

    async def _handle_websocket_message(self, data: str):
        """Handle incoming WebSocket message from BitChat."""
        try:
            msg_data = json.loads(data)
            msg_type = msg_data.get("type")

            if msg_type == "pong":
                # Pong response to ping
                pass

            elif msg_type in ["message", "group_message"]:
                # Convert BitChat message to P2P format
                bitchat_msg = msg_data.get("data", {})

                # Convert hex content back to bytes
                content_hex = bitchat_msg.get("content", "")
                try:
                    payload = bytes.fromhex(content_hex)
                except ValueError:
                    payload = content_hex.encode("utf-8")

                p2p_message = {
                    "message_id": bitchat_msg.get("message_id"),
                    "sender_id": bitchat_msg.get("from_peer_id"),
                    "receiver_id": bitchat_msg.get("to_peer_id", self.node_id),
                    "payload": payload,
                    "message_type": "data",
                    "priority": 3,
                    "transport_type": "bitchat_ble",
                    "timestamp": bitchat_msg.get("sent_at"),
                }

                # Notify handlers
                await self._notify_handlers(p2p_message)

                self.messages_received += 1
                self.last_activity = time.time()

                # Send acknowledgment
                if bitchat_msg.get("message_id"):
                    await self.ws.send_json({
                        "type": "ack",
                        "message_id": bitchat_msg["message_id"]
                    })

        except Exception as e:
            logger.error(f"Error handling BitChat WebSocket message: {e}")
            self.errors.append(f"WebSocket message error: {str(e)}")
