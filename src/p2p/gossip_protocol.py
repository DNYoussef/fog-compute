"""
Gossip Protocol for BitChat Group Messaging
Implements epidemic broadcast with vector clocks for message ordering
"""
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import random
import logging
import json
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class VectorClock:
    """Vector clock for causal ordering of messages"""
    clocks: Dict[str, int] = field(default_factory=dict)

    def increment(self, peer_id: str):
        """Increment clock for a peer"""
        self.clocks[peer_id] = self.clocks.get(peer_id, 0) + 1

    def update(self, other: 'VectorClock'):
        """Merge with another vector clock"""
        for peer_id, value in other.clocks.items():
            self.clocks[peer_id] = max(self.clocks.get(peer_id, 0), value)

    def happens_before(self, other: 'VectorClock') -> bool:
        """Check if this clock happens before another"""
        less_or_equal = all(
            self.clocks.get(k, 0) <= other.clocks.get(k, 0)
            for k in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        strictly_less = any(
            self.clocks.get(k, 0) < other.clocks.get(k, 0)
            for k in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        return less_or_equal and strictly_less

    def concurrent_with(self, other: 'VectorClock') -> bool:
        """Check if clocks are concurrent (no causal relationship)"""
        return not self.happens_before(other) and not other.happens_before(self)

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for serialization"""
        return self.clocks.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'VectorClock':
        """Create from dictionary"""
        return cls(clocks=data.copy())


@dataclass
class GossipMessage:
    """Message in gossip protocol"""
    message_id: str
    group_id: str
    sender_id: str
    content: str
    vector_clock: VectorClock
    timestamp: datetime
    hop_count: int = 0
    seen_by: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict:
        """Convert to dictionary for transmission"""
        return {
            'message_id': self.message_id,
            'group_id': self.group_id,
            'sender_id': self.sender_id,
            'content': self.content,
            'vector_clock': self.vector_clock.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'hop_count': self.hop_count,
            'seen_by': list(self.seen_by)
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GossipMessage':
        """Create from dictionary"""
        return cls(
            message_id=data['message_id'],
            group_id=data['group_id'],
            sender_id=data['sender_id'],
            content=data['content'],
            vector_clock=VectorClock.from_dict(data['vector_clock']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            hop_count=data.get('hop_count', 0),
            seen_by=set(data.get('seen_by', []))
        )


class GossipProtocol:
    """
    Epidemic broadcast protocol for group messaging

    Features:
    - Probabilistic message propagation
    - Vector clock-based message ordering
    - Conflict resolution for concurrent messages
    - Anti-entropy for reliability
    - Configurable fanout and TTL
    """

    def __init__(
        self,
        peer_id: str,
        fanout: int = 3,
        gossip_interval: float = 0.1,
        anti_entropy_interval: float = 5.0,
        message_ttl: int = 100
    ):
        """
        Initialize gossip protocol

        Args:
            peer_id: This peer's identifier
            fanout: Number of peers to gossip to per round
            gossip_interval: Seconds between gossip rounds
            anti_entropy_interval: Seconds between anti-entropy sync
            message_ttl: Maximum hop count for messages
        """
        self.peer_id = peer_id
        self.fanout = fanout
        self.gossip_interval = gossip_interval
        self.anti_entropy_interval = anti_entropy_interval
        self.message_ttl = message_ttl

        # State
        self.vector_clock = VectorClock()
        self.message_buffer: Dict[str, GossipMessage] = {}
        self.delivered_messages: Dict[str, GossipMessage] = {}
        self.group_members: Dict[str, Set[str]] = {}  # group_id -> set of peer_ids

        # Metrics
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.duplicate_messages = 0
        self.propagation_delays: List[float] = []

        # Background tasks
        self._gossip_task: Optional[asyncio.Task] = None
        self._anti_entropy_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(f"Gossip protocol initialized for peer {peer_id}")

    async def start(self):
        """Start gossip background tasks"""
        if self._running:
            return

        self._running = True
        self._gossip_task = asyncio.create_task(self._gossip_loop())
        self._anti_entropy_task = asyncio.create_task(self._anti_entropy_loop())
        logger.info(f"Gossip protocol started for peer {self.peer_id}")

    async def stop(self):
        """Stop gossip background tasks"""
        self._running = False

        if self._gossip_task:
            self._gossip_task.cancel()
            try:
                await self._gossip_task
            except asyncio.CancelledError:
                pass

        if self._anti_entropy_task:
            self._anti_entropy_task.cancel()
            try:
                await self._anti_entropy_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Gossip protocol stopped for peer {self.peer_id}")

    def join_group(self, group_id: str, members: List[str]):
        """Join a group with initial members"""
        self.group_members[group_id] = set(members)
        logger.info(f"Peer {self.peer_id} joined group {group_id} with {len(members)} members")

    def leave_group(self, group_id: str):
        """Leave a group"""
        if group_id in self.group_members:
            del self.group_members[group_id]
            logger.info(f"Peer {self.peer_id} left group {group_id}")

    def add_member(self, group_id: str, peer_id: str):
        """Add a member to a group"""
        if group_id not in self.group_members:
            self.group_members[group_id] = set()
        self.group_members[group_id].add(peer_id)
        logger.info(f"Added {peer_id} to group {group_id}")

    def remove_member(self, group_id: str, peer_id: str):
        """Remove a member from a group"""
        if group_id in self.group_members:
            self.group_members[group_id].discard(peer_id)
            logger.info(f"Removed {peer_id} from group {group_id}")

    async def broadcast_message(
        self,
        group_id: str,
        content: str,
        message_id: Optional[str] = None
    ) -> GossipMessage:
        """
        Broadcast a message to a group

        Args:
            group_id: Group identifier
            content: Message content
            message_id: Optional message ID (generated if not provided)

        Returns:
            The created gossip message
        """
        if group_id not in self.group_members:
            raise ValueError(f"Not a member of group {group_id}")

        # Generate message ID if not provided
        if message_id is None:
            message_id = self._generate_message_id(group_id, content)

        # Increment vector clock
        self.vector_clock.increment(self.peer_id)

        # Create message
        message = GossipMessage(
            message_id=message_id,
            group_id=group_id,
            sender_id=self.peer_id,
            content=content,
            vector_clock=VectorClock.from_dict(self.vector_clock.to_dict()),
            timestamp=datetime.utcnow(),
            hop_count=0,
            seen_by={self.peer_id}
        )

        # Add to buffer
        self.message_buffer[message_id] = message

        # Immediately gossip to fanout peers
        await self._gossip_message(message)

        # Mark as delivered
        self.delivered_messages[message_id] = message

        logger.info(f"Broadcast message {message_id} to group {group_id}")
        return message

    async def receive_message(self, message_dict: Dict) -> Optional[GossipMessage]:
        """
        Receive a gossip message from another peer

        Args:
            message_dict: Message dictionary

        Returns:
            The message if it's new and should be delivered, None otherwise
        """
        message = GossipMessage.from_dict(message_dict)
        self.total_messages_received += 1

        # Check if already seen
        if message.message_id in self.delivered_messages:
            self.duplicate_messages += 1
            return None

        # Check if already in buffer
        if message.message_id in self.message_buffer:
            # Update seen_by and hop_count
            existing = self.message_buffer[message.message_id]
            existing.seen_by.update(message.seen_by)
            existing.hop_count = max(existing.hop_count, message.hop_count)
            return None

        # Check TTL
        if message.hop_count >= self.message_ttl:
            logger.warning(f"Message {message.message_id} exceeded TTL")
            return None

        # Update vector clock
        self.vector_clock.update(message.vector_clock)

        # Mark as seen
        message.seen_by.add(self.peer_id)
        message.hop_count += 1

        # Add to buffer
        self.message_buffer[message.message_id] = message

        # Try to deliver based on causal ordering
        delivered = self._try_deliver_messages()

        # Gossip to other peers
        await self._gossip_message(message)

        logger.info(f"Received message {message.message_id}, delivered {len(delivered)} messages")

        # Return if this message was delivered
        return message if message.message_id in [m.message_id for m in delivered] else None

    def _try_deliver_messages(self) -> List[GossipMessage]:
        """
        Try to deliver buffered messages respecting causal order

        Returns:
            List of delivered messages
        """
        delivered = []

        while True:
            deliverable = None

            for msg_id, message in self.message_buffer.items():
                # Check if all causally prior messages have been delivered
                can_deliver = True
                for peer_id, clock_value in message.vector_clock.clocks.items():
                    if peer_id == message.sender_id:
                        # Check if we have all prior messages from sender
                        our_clock = self.vector_clock.clocks.get(peer_id, 0)
                        if our_clock < clock_value - 1:
                            can_deliver = False
                            break
                    else:
                        # Check if we're up to date with other peers
                        our_clock = self.vector_clock.clocks.get(peer_id, 0)
                        if our_clock < clock_value:
                            can_deliver = False
                            break

                if can_deliver:
                    deliverable = message
                    break

            if deliverable is None:
                break

            # Deliver message
            self.delivered_messages[deliverable.message_id] = deliverable
            del self.message_buffer[deliverable.message_id]
            delivered.append(deliverable)

            # Update vector clock
            self.vector_clock.increment(deliverable.sender_id)

            # Track propagation delay
            delay = (datetime.utcnow() - deliverable.timestamp).total_seconds()
            self.propagation_delays.append(delay)

        return delivered

    async def _gossip_loop(self):
        """Background gossip loop"""
        while self._running:
            try:
                # Gossip all buffered messages
                for message in list(self.message_buffer.values()):
                    await self._gossip_message(message)

                await asyncio.sleep(self.gossip_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in gossip loop: {e}")

    async def _gossip_message(self, message: GossipMessage):
        """
        Gossip a message to random peers

        Args:
            message: Message to gossip
        """
        if message.group_id not in self.group_members:
            return

        # Get peers who haven't seen the message
        members = self.group_members[message.group_id]
        unseen = members - message.seen_by - {self.peer_id}

        if not unseen:
            return

        # Select random subset (fanout)
        targets = random.sample(list(unseen), min(self.fanout, len(unseen)))

        # Send to targets (would integrate with actual P2P transport)
        for target in targets:
            try:
                # This would call actual P2P send method
                # For now, just log
                logger.debug(f"Gossiping message {message.message_id} to {target}")
                self.total_messages_sent += 1
            except Exception as e:
                logger.error(f"Error gossiping to {target}: {e}")

    async def _anti_entropy_loop(self):
        """Background anti-entropy synchronization loop"""
        while self._running:
            try:
                await self._anti_entropy_sync()
                await asyncio.sleep(self.anti_entropy_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in anti-entropy loop: {e}")

    async def _anti_entropy_sync(self):
        """
        Perform anti-entropy synchronization

        Exchanges message summaries with random peers to detect missing messages
        """
        for group_id, members in self.group_members.items():
            if not members:
                continue

            # Select random peer
            peer_id = random.choice(list(members - {self.peer_id}))

            # Exchange message IDs (would integrate with actual P2P transport)
            # This ensures eventual consistency
            logger.debug(f"Anti-entropy sync with {peer_id} for group {group_id}")

    def _generate_message_id(self, group_id: str, content: str) -> str:
        """Generate unique message ID"""
        data = f"{group_id}:{self.peer_id}:{datetime.utcnow().isoformat()}:{content}"
        return hashlib.sha256(data.encode()).hexdigest()

    def get_metrics(self) -> Dict:
        """
        Get protocol metrics

        Returns:
            Dictionary with metrics
        """
        avg_delay = (
            sum(self.propagation_delays) / len(self.propagation_delays)
            if self.propagation_delays else 0
        )

        return {
            'peer_id': self.peer_id,
            'total_messages_sent': self.total_messages_sent,
            'total_messages_received': self.total_messages_received,
            'duplicate_messages': self.duplicate_messages,
            'duplicate_rate': (
                self.duplicate_messages / self.total_messages_received
                if self.total_messages_received > 0 else 0
            ),
            'average_propagation_delay_ms': avg_delay * 1000,
            'buffered_messages': len(self.message_buffer),
            'delivered_messages': len(self.delivered_messages),
            'groups': len(self.group_members),
            'vector_clock': self.vector_clock.to_dict()
        }
