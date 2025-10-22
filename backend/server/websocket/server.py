"""
Production-grade WebSocket Server for Real-time Updates
Handles 1000+ concurrent connections with room-based subscriptions
"""
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, Set, Any, Optional, List
import asyncio
import logging
import json
from datetime import datetime
from collections import defaultdict
import time

from ..auth.jwt_utils import verify_token
from ..auth.dependencies import get_current_user

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections with room-based subscriptions
    Supports 1000+ concurrent connections with efficient broadcasting
    """

    def __init__(self):
        # Active connections: {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}

        # Room subscriptions: {room_name: Set[connection_id]}
        self.rooms: Dict[str, Set[str]] = defaultdict(set)

        # Connection metadata: {connection_id: metadata}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Heartbeat tracking: {connection_id: last_ping_time}
        self.heartbeats: Dict[str, float] = {}

        # Connection stats
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "total_messages": 0,
            "rooms_created": 0
        }

        # Heartbeat configuration
        self.heartbeat_interval = 30.0  # seconds
        self.heartbeat_timeout = 60.0  # seconds

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background tasks"""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
        logger.info("WebSocket connection manager started")

    async def stop(self):
        """Stop background tasks and close all connections"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Close all active connections
        for connection_id in list(self.active_connections.keys()):
            await self.disconnect(connection_id)

        logger.info("WebSocket connection manager stopped")

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Accept and register a new WebSocket connection

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            user_id: Optional authenticated user ID
            metadata: Optional connection metadata
        """
        await websocket.accept()

        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "user_id": user_id,
            "connected_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "subscribed_rooms": []
        }
        self.heartbeats[connection_id] = time.time()

        self.stats["total_connections"] += 1
        self.stats["active_connections"] = len(self.active_connections)

        logger.info(f"WebSocket connected: {connection_id} (user: {user_id})")

        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.now().isoformat()
        }, connection_id)

    async def disconnect(self, connection_id: str):
        """
        Disconnect and cleanup a WebSocket connection

        Args:
            connection_id: Connection to disconnect
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]

            # Unsubscribe from all rooms
            for room in list(self.rooms.keys()):
                if connection_id in self.rooms[room]:
                    self.rooms[room].remove(connection_id)
                    if not self.rooms[room]:
                        del self.rooms[room]

            # Cleanup
            del self.active_connections[connection_id]
            del self.connection_metadata[connection_id]
            del self.heartbeats[connection_id]

            self.stats["active_connections"] = len(self.active_connections)

            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket {connection_id}: {e}")

            logger.info(f"WebSocket disconnected: {connection_id}")

    async def subscribe_to_room(self, connection_id: str, room: str):
        """
        Subscribe a connection to a room

        Args:
            connection_id: Connection to subscribe
            room: Room name
        """
        if connection_id not in self.active_connections:
            raise ValueError(f"Connection {connection_id} not found")

        self.rooms[room].add(connection_id)

        if room not in self.connection_metadata[connection_id]["subscribed_rooms"]:
            self.connection_metadata[connection_id]["subscribed_rooms"].append(room)

        if len(self.rooms[room]) == 1:
            self.stats["rooms_created"] += 1

        logger.info(f"Connection {connection_id} subscribed to room: {room}")

        await self.send_personal_message({
            "type": "subscription_confirmed",
            "room": room,
            "timestamp": datetime.now().isoformat()
        }, connection_id)

    async def unsubscribe_from_room(self, connection_id: str, room: str):
        """
        Unsubscribe a connection from a room

        Args:
            connection_id: Connection to unsubscribe
            room: Room name
        """
        if room in self.rooms and connection_id in self.rooms[room]:
            self.rooms[room].remove(connection_id)

            if not self.rooms[room]:
                del self.rooms[room]

            if room in self.connection_metadata[connection_id]["subscribed_rooms"]:
                self.connection_metadata[connection_id]["subscribed_rooms"].remove(room)

            logger.info(f"Connection {connection_id} unsubscribed from room: {room}")

            await self.send_personal_message({
                "type": "unsubscription_confirmed",
                "room": room,
                "timestamp": datetime.now().isoformat()
            }, connection_id)

    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """
        Send message to a specific connection

        Args:
            message: Message to send
            connection_id: Target connection
        """
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_json(message)
                self.stats["total_messages"] += 1
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                await self.disconnect(connection_id)

    async def broadcast_to_room(self, message: Dict[str, Any], room: str):
        """
        Broadcast message to all connections in a room

        Args:
            message: Message to broadcast
            room: Target room
        """
        if room not in self.rooms:
            return

        # Add room metadata to message
        message_with_metadata = {
            **message,
            "room": room,
            "timestamp": datetime.now().isoformat()
        }

        # Broadcast to all room members concurrently
        tasks = []
        for connection_id in list(self.rooms[room]):
            tasks.append(self.send_personal_message(message_with_metadata, connection_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.debug(f"Broadcasted to room '{room}': {len(tasks)} connections")

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """
        Broadcast message to all active connections

        Args:
            message: Message to broadcast
        """
        tasks = []
        for connection_id in list(self.active_connections.keys()):
            tasks.append(self.send_personal_message(message, connection_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_ping(self, connection_id: str):
        """
        Handle heartbeat ping from client

        Args:
            connection_id: Connection that sent ping
        """
        if connection_id in self.heartbeats:
            self.heartbeats[connection_id] = time.time()
            await self.send_personal_message({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            }, connection_id)

    async def _heartbeat_monitor(self):
        """Background task to send heartbeat pings"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                # Send ping to all connections
                for connection_id in list(self.active_connections.keys()):
                    try:
                        await self.send_personal_message({
                            "type": "ping",
                            "timestamp": datetime.now().isoformat()
                        }, connection_id)
                    except Exception as e:
                        logger.error(f"Heartbeat error for {connection_id}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")

    async def _cleanup_stale_connections(self):
        """Background task to cleanup stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = time.time()
                stale_connections = []

                for connection_id, last_ping in self.heartbeats.items():
                    if now - last_ping > self.heartbeat_timeout:
                        stale_connections.append(connection_id)

                for connection_id in stale_connections:
                    logger.warning(f"Disconnecting stale connection: {connection_id}")
                    await self.disconnect(connection_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            **self.stats,
            "rooms": {
                room: len(connections)
                for room, connections in self.rooms.items()
            }
        }

    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific connection"""
        if connection_id in self.connection_metadata:
            return self.connection_metadata[connection_id]
        return None


# Global connection manager instance
connection_manager = ConnectionManager()
