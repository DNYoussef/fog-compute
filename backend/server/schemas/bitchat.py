"""
BitChat Pydantic Schemas
Request/Response validation models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..constants import MAX_ATTACHMENT_SIZE


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


# ============================================================================
# Group Chat Schemas
# ============================================================================

class GroupCreateRequest(BaseModel):
    """Request to create a group"""
    name: str = Field(..., description="Group name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Group description")
    created_by: str = Field(..., description="Creator peer ID")
    initial_members: List[str] = Field(default_factory=list, description="Initial member peer IDs")


class GroupResponse(BaseModel):
    """Group information response"""
    id: str
    group_id: str
    name: str
    description: Optional[str]
    created_by: str
    created_at: str
    is_active: bool
    member_count: int
    message_count: int
    last_sync: str


class GroupMemberAddRequest(BaseModel):
    """Request to add a member to a group"""
    peer_id: str = Field(..., description="Peer ID to add")
    role: str = Field(default="member", description="Member role (admin, moderator, member)")


class GroupMemberResponse(BaseModel):
    """Group membership response"""
    id: str
    group_id: str
    peer_id: str
    role: str
    joined_at: str
    is_active: bool
    messages_sent: int


class GroupMessageSendRequest(BaseModel):
    """Request to send a group message"""
    from_peer_id: str = Field(..., description="Sender peer ID")
    content: str = Field(..., description="Encrypted message content")
    encryption_algorithm: str = Field(default="AES-256-GCM", description="Encryption algorithm")
    nonce: Optional[str] = Field(None, description="Encryption nonce/IV")


# ============================================================================
# File Transfer Schemas
# ============================================================================

class FileUploadInitRequest(BaseModel):
    """Request to initialize file upload"""
    filename: str = Field(..., description="File name", min_length=1)
    file_size: int = Field(..., description="File size in bytes", gt=0, le=MAX_ATTACHMENT_SIZE)  # Max 1GB
    uploaded_by: str = Field(..., description="Uploader peer ID")
    mime_type: Optional[str] = Field(None, description="MIME type")


class FileTransferResponse(BaseModel):
    """File transfer information response"""
    id: str
    file_id: str
    filename: str
    file_size: int
    mime_type: Optional[str]
    chunk_size: int
    total_chunks: int
    uploaded_chunks: int
    uploaded_by: str
    status: str
    progress: float
    created_at: str
    completed_at: Optional[str]
    download_sources: List[str]


class ChunkUploadRequest(BaseModel):
    """Request to upload a chunk"""
    chunk_index: int = Field(..., description="Chunk index", ge=0)
    # chunk_data will be sent as multipart form data


class ChunkStatusResponse(BaseModel):
    """Chunk status response"""
    chunk_index: int
    chunk_hash: str
    chunk_size: int
    uploaded: bool
    available_from: List[str]


class FileDownloadRequest(BaseModel):
    """Request to download a file"""
    sources: Optional[List[str]] = Field(None, description="Preferred peer sources")
