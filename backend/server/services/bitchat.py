"""
BitChat Service
Handles P2P messaging with encryption and persistence
"""
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from fastapi import WebSocket
import logging
import uuid
import json

from ..models.database import Peer, Message
from ..database import get_db
from . import bitchat_groups

logger = logging.getLogger(__name__)


class BitChatService:
    """
    BitChat P2P Messaging Service

    Provides:
    - Peer registration and management
    - End-to-end encrypted messaging
    - Message persistence and history
    - WebSocket real-time communication
    - Group chat support
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.peer_sessions: Dict[str, dict] = {}
        logger.info("BitChat service initialized")

    async def register_peer(
        self,
        peer_id: str,
        public_key: str,
        display_name: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict:
        """
        Register a new peer in the network

        Args:
            peer_id: Unique peer identifier
            public_key: Peer's public key for encryption
            display_name: Optional display name
            db: Database session

        Returns:
            Dictionary with peer information
        """
        try:
            # Check if peer already exists
            result = await db.execute(
                select(Peer).where(Peer.peer_id == peer_id)
            )
            existing_peer = result.scalar_one_or_none()

            if existing_peer:
                # Update existing peer
                existing_peer.public_key = public_key
                existing_peer.display_name = display_name or existing_peer.display_name
                existing_peer.last_seen = datetime.now(timezone.utc)
                existing_peer.is_online = True
                await db.commit()
                await db.refresh(existing_peer)

                logger.info(f"Updated existing peer: {peer_id}")
                return existing_peer.to_dict()

            # Create new peer
            new_peer = Peer(
                peer_id=peer_id,
                public_key=public_key,
                display_name=display_name,
                is_online=True,
                last_seen=datetime.now(timezone.utc)
            )

            db.add(new_peer)
            await db.commit()
            await db.refresh(new_peer)

            logger.info(f"Registered new peer: {peer_id}")
            return new_peer.to_dict()

        except Exception as e:
            logger.error(f"Error registering peer {peer_id}: {e}")
            await db.rollback()
            raise

    async def update_peer_status(
        self,
        peer_id: str,
        is_online: bool,
        db: AsyncSession
    ) -> bool:
        """
        Update peer online status

        Args:
            peer_id: Peer identifier
            is_online: Online status
            db: Database session

        Returns:
            Success status
        """
        try:
            result = await db.execute(
                select(Peer).where(Peer.peer_id == peer_id)
            )
            peer = result.scalar_one_or_none()

            if peer:
                peer.is_online = is_online
                peer.last_seen = datetime.utcnow()
                await db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating peer status: {e}")
            await db.rollback()
            return False

    async def list_peers(
        self,
        online_only: bool = False,
        db: AsyncSession = None
    ) -> List[Dict]:
        """
        Get list of all peers

        Args:
            online_only: Filter to only online peers
            db: Database session

        Returns:
            List of peer dictionaries
        """
        try:
            query = select(Peer)

            if online_only:
                query = query.where(Peer.is_online == True)

            result = await db.execute(query.order_by(desc(Peer.last_seen)))
            peers = result.scalars().all()

            return [peer.to_dict() for peer in peers]

        except Exception as e:
            logger.error(f"Error listing peers: {e}")
            return []

    async def send_message(
        self,
        from_peer_id: str,
        to_peer_id: Optional[str],
        content: str,
        group_id: Optional[str] = None,
        encryption_algorithm: str = "AES-256-GCM",
        nonce: Optional[str] = None,
        ttl: int = 3600,
        db: AsyncSession = None
    ) -> Dict:
        """
        Send an encrypted message

        Args:
            from_peer_id: Sender peer ID
            to_peer_id: Recipient peer ID (None for group messages)
            content: Encrypted message content
            group_id: Optional group chat ID
            encryption_algorithm: Encryption algorithm used
            nonce: Encryption nonce/IV
            ttl: Time to live in seconds
            db: Database session

        Returns:
            Message dictionary
        """
        try:
            # Generate unique message ID
            message_id = str(uuid.uuid4())

            # Create message record
            new_message = Message(
                message_id=message_id,
                from_peer_id=from_peer_id,
                to_peer_id=to_peer_id,
                group_id=group_id,
                content=content,
                encryption_algorithm=encryption_algorithm,
                nonce=nonce,
                status='sent',
                ttl=ttl
            )

            db.add(new_message)

            # Update sender stats
            sender_result = await db.execute(
                select(Peer).where(Peer.peer_id == from_peer_id)
            )
            sender = sender_result.scalar_one_or_none()
            if sender:
                sender.messages_sent += 1

            # Update recipient stats
            if to_peer_id:
                recipient_result = await db.execute(
                    select(Peer).where(Peer.peer_id == to_peer_id)
                )
                recipient = recipient_result.scalar_one_or_none()
                if recipient:
                    recipient.messages_received += 1

            await db.commit()
            await db.refresh(new_message)

            # Try to deliver via WebSocket if recipient is online
            if to_peer_id and to_peer_id in self.active_connections:
                await self._deliver_message_ws(to_peer_id, new_message.to_dict())

            logger.info(f"Message sent: {message_id} from {from_peer_id} to {to_peer_id or group_id}")
            return new_message.to_dict()

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await db.rollback()
            raise

    async def get_conversation(
        self,
        peer_id: str,
        other_peer_id: str,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = None
    ) -> List[Dict]:
        """
        Get conversation history between two peers

        Args:
            peer_id: First peer ID
            other_peer_id: Second peer ID
            limit: Maximum messages to return
            offset: Offset for pagination
            db: Database session

        Returns:
            List of message dictionaries
        """
        try:
            query = select(Message).where(
                or_(
                    and_(
                        Message.from_peer_id == peer_id,
                        Message.to_peer_id == other_peer_id
                    ),
                    and_(
                        Message.from_peer_id == other_peer_id,
                        Message.to_peer_id == peer_id
                    )
                )
            ).order_by(desc(Message.sent_at)).limit(limit).offset(offset)

            result = await db.execute(query)
            messages = result.scalars().all()

            # Return in chronological order (oldest first)
            return [msg.to_dict() for msg in reversed(messages)]

        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return []

    async def get_group_messages(
        self,
        group_id: str,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = None
    ) -> List[Dict]:
        """
        Get messages for a group chat

        Args:
            group_id: Group chat ID
            limit: Maximum messages to return
            offset: Offset for pagination
            db: Database session

        Returns:
            List of message dictionaries
        """
        try:
            query = select(Message).where(
                Message.group_id == group_id
            ).order_by(desc(Message.sent_at)).limit(limit).offset(offset)

            result = await db.execute(query)
            messages = result.scalars().all()

            return [msg.to_dict() for msg in reversed(messages)]

        except Exception as e:
            logger.error(f"Error getting group messages: {e}")
            return []

    async def mark_delivered(
        self,
        message_id: str,
        db: AsyncSession
    ) -> bool:
        """
        Mark a message as delivered

        Args:
            message_id: Message ID
            db: Database session

        Returns:
            Success status
        """
        try:
            result = await db.execute(
                select(Message).where(Message.message_id == message_id)
            )
            message = result.scalar_one_or_none()

            if message:
                message.status = 'delivered'
                message.delivered_at = datetime.utcnow()
                await db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"Error marking message delivered: {e}")
            await db.rollback()
            return False

    async def connect_websocket(self, peer_id: str, websocket: WebSocket):
        """
        Register WebSocket connection for peer

        Args:
            peer_id: Peer identifier
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.active_connections[peer_id] = websocket
        logger.info(f"WebSocket connected for peer: {peer_id}")

        # Update peer status to online
        async for db in get_db():
            await self.update_peer_status(peer_id, True, db)
            break

    async def disconnect_websocket(self, peer_id: str):
        """
        Remove WebSocket connection for peer

        Args:
            peer_id: Peer identifier
        """
        if peer_id in self.active_connections:
            del self.active_connections[peer_id]
            logger.info(f"WebSocket disconnected for peer: {peer_id}")

            # Update peer status to offline
            async for db in get_db():
                await self.update_peer_status(peer_id, False, db)
                break

    async def _deliver_message_ws(self, peer_id: str, message: Dict):
        """
        Deliver message via WebSocket

        Args:
            peer_id: Recipient peer ID
            message: Message dictionary
        """
        if peer_id in self.active_connections:
            try:
                websocket = self.active_connections[peer_id]
                await websocket.send_json({
                    'type': 'message',
                    'data': message
                })
            except Exception as e:
                logger.error(f"Error delivering message via WebSocket: {e}")

    async def broadcast_to_group(self, group_id: str, message: Dict):
        """
        Broadcast message to all online group members

        Args:
            group_id: Group ID
            message: Message dictionary
        """
        # Get all peers in the group (would need a group_members table in production)
        # For now, broadcast to all connected peers
        for peer_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json({
                    'type': 'group_message',
                    'group_id': group_id,
                    'data': message
                })
            except Exception as e:
                logger.error(f"Error broadcasting to {peer_id}: {e}")

    async def get_stats(self, db: AsyncSession = None) -> Dict:
        """
        Get BitChat service statistics

        Args:
            db: Database session

        Returns:
            Statistics dictionary
        """
        try:
            # Count total peers
            total_peers_result = await db.execute(
                select(func.count()).select_from(Peer)
            )
            total_peers = total_peers_result.scalar()

            # Count online peers
            online_peers_result = await db.execute(
                select(func.count()).select_from(Peer).where(Peer.is_online == True)
            )
            online_peers = online_peers_result.scalar()

            # Count total messages
            total_messages_result = await db.execute(
                select(func.count()).select_from(Message)
            )
            total_messages = total_messages_result.scalar()

            # Count messages in last 24 hours
            last_24h = datetime.utcnow() - timedelta(hours=24)
            recent_messages_result = await db.execute(
                select(func.count()).select_from(Message).where(
                    Message.sent_at >= last_24h
                )
            )
            recent_messages = recent_messages_result.scalar()

            return {
                'total_peers': total_peers,
                'online_peers': online_peers,
                'active_connections': len(self.active_connections),
                'total_messages': total_messages,
                'messages_24h': recent_messages,
                'status': 'operational'
            }

        except Exception as e:
            logger.error(f"Error getting BitChat stats: {e}")
            return {
                'total_peers': 0,
                'online_peers': 0,
                'active_connections': len(self.active_connections),
                'total_messages': 0,
                'messages_24h': 0,
                'status': 'error'
            }

    # ========================================================================
    # Group Management Methods
    # ========================================================================

    async def create_group(
        self,
        name: str,
        description: Optional[str],
        created_by: str,
        initial_members: List[str],
        db: AsyncSession
    ) -> Dict:
        """Create a new group chat"""
        return await bitchat_groups.create_group(
            name=name,
            description=description,
            created_by=created_by,
            initial_members=initial_members,
            db=db
        )

    async def list_groups(
        self,
        peer_id: Optional[str],
        db: AsyncSession
    ) -> List[Dict]:
        """List groups (optionally filtered by peer membership)"""
        return await bitchat_groups.list_groups(peer_id=peer_id, db=db)

    async def get_group(
        self,
        group_id: str,
        db: AsyncSession
    ) -> Optional[Dict]:
        """Get group information"""
        return await bitchat_groups.get_group(group_id=group_id, db=db)

    async def add_group_member(
        self,
        group_id: str,
        peer_id: str,
        role: str,
        db: AsyncSession
    ) -> Dict:
        """Add a member to a group"""
        return await bitchat_groups.add_group_member(
            group_id=group_id,
            peer_id=peer_id,
            role=role,
            db=db
        )

    async def remove_group_member(
        self,
        group_id: str,
        peer_id: str,
        db: AsyncSession
    ) -> bool:
        """Remove a member from a group"""
        return await bitchat_groups.remove_group_member(
            group_id=group_id,
            peer_id=peer_id,
            db=db
        )

    async def list_group_members(
        self,
        group_id: str,
        db: AsyncSession
    ) -> List[Dict]:
        """List members of a group"""
        return await bitchat_groups.list_group_members(group_id=group_id, db=db)


# Singleton instance
bitchat_service = BitChatService()
