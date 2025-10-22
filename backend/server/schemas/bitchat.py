"""
BitChat Pydantic Schemas
Request/Response validation models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PeerRegisterRequest(BaseModel):
    """Request to register a new peer"""
    peer_id: str = Field(..., description="Unique peer identifier")
    public_key: str = Field(..., description="Peer's public key for encryption")
    display_name: Optional[str] = Field(None, description="Optional display name")


class PeerResponse(BaseModel):
    """Peer information response"""
    id: str
    peer_id: str
    public_key: str
    display_name: Optional[str]
    last_seen: str
    is_online: bool
    trust_score: float
    messages_sent: int
    messages_received: int
    created_at: str


class MessageSendRequest(BaseModel):
    """Request to send a message"""
    from_peer_id: str = Field(..., description="Sender peer ID")
    to_peer_id: Optional[str] = Field(None, description="Recipient peer ID (null for group)")
    group_id: Optional[str] = Field(None, description="Group chat ID")
    content: str = Field(..., description="Encrypted message content")
    encryption_algorithm: str = Field(default="AES-256-GCM", description="Encryption algorithm")
    nonce: Optional[str] = Field(None, description="Encryption nonce/IV")
    ttl: int = Field(default=3600, description="Time to live in seconds")


class MessageResponse(BaseModel):
    """Message information response"""
    id: str
    message_id: str
    from_peer_id: str
    to_peer_id: Optional[str]
    group_id: Optional[str]
    content: str
    encryption_algorithm: str
    nonce: Optional[str]
    status: str
    sent_at: str
    delivered_at: Optional[str]
    ttl: int
    hop_count: int


class ConversationRequest(BaseModel):
    """Request to get conversation history"""
    peer_id: str = Field(..., description="First peer ID")
    other_peer_id: str = Field(..., description="Second peer ID")
    limit: int = Field(default=50, description="Maximum messages to return")
    offset: int = Field(default=0, description="Offset for pagination")


class GroupMessagesRequest(BaseModel):
    """Request to get group messages"""
    group_id: str = Field(..., description="Group chat ID")
    limit: int = Field(default=50, description="Maximum messages to return")
    offset: int = Field(default=0, description="Offset for pagination")


class BitChatStatsResponse(BaseModel):
    """BitChat service statistics"""
    total_peers: int
    online_peers: int
    active_connections: int
    total_messages: int
    messages_24h: int
    status: str
