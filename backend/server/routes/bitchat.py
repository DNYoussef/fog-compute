"""
BitChat API Routes
Endpoints for P2P messaging network
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone
import logging

from ..database import get_db
from ..services.bitchat import bitchat_service
from ..schemas.bitchat import (
    PeerRegisterRequest,
    PeerResponse,
    MessageSendRequest,
    MessageResponse,
    ConversationRequest,
    GroupMessagesRequest,
    BitChatStatsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bitchat", tags=["BitChat"])


# ============================================================================
# Peer Management Endpoints
# ============================================================================

@router.post("/peers/register", response_model=PeerResponse, status_code=status.HTTP_201_CREATED)
async def register_peer(
    request: PeerRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new peer in the BitChat network

    Creates a new peer or updates existing peer with new public key.
    The peer will be marked as online upon registration.

    Args:
        request: Peer registration data
        db: Database session

    Returns:
        Registered peer information

    Raises:
        HTTPException: If registration fails
    """
    try:
        peer = await bitchat_service.register_peer(
            peer_id=request.peer_id,
            public_key=request.public_key,
            display_name=request.display_name,
            db=db
        )
        return peer
    except Exception as e:
        logger.error(f"Peer registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register peer: {str(e)}"
        )


@router.get("/peers", response_model=List[PeerResponse])
async def list_peers(
    online_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List all peers in the network

    Args:
        online_only: Filter to only online peers
        db: Database session

    Returns:
        List of peers
    """
    peers = await bitchat_service.list_peers(online_only=online_only, db=db)
    return peers


@router.get("/peers/{peer_id}", response_model=PeerResponse)
async def get_peer(
    peer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get information about a specific peer

    Args:
        peer_id: Peer identifier
        db: Database session

    Returns:
        Peer information

    Raises:
        HTTPException: If peer not found
    """
    from sqlalchemy import select
    from ..models.database import Peer

    result = await db.execute(
        select(Peer).where(Peer.peer_id == peer_id)
    )
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found"
        )

    return peer.to_dict()


@router.put("/peers/{peer_id}/status")
async def update_peer_status(
    peer_id: str,
    is_online: bool,
    db: AsyncSession = Depends(get_db)
):
    """
    Update peer online status

    Args:
        peer_id: Peer identifier
        is_online: Online status
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If update fails
    """
    success = await bitchat_service.update_peer_status(peer_id, is_online, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found"
        )

    return {"message": f"Peer {peer_id} status updated", "is_online": is_online}


# ============================================================================
# Messaging Endpoints
# ============================================================================

@router.post("/messages/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    request: MessageSendRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send an encrypted message

    Sends a message to a specific peer or group. Message is persisted
    and delivered via WebSocket if recipient is online.

    Args:
        request: Message data
        db: Database session

    Returns:
        Sent message information

    Raises:
        HTTPException: If send fails
    """
    try:
        message = await bitchat_service.send_message(
            from_peer_id=request.from_peer_id,
            to_peer_id=request.to_peer_id,
            content=request.content,
            group_id=request.group_id,
            encryption_algorithm=request.encryption_algorithm,
            nonce=request.nonce,
            ttl=request.ttl,
            db=db
        )
        return message
    except Exception as e:
        logger.error(f"Message send failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.post("/messages/conversation", response_model=List[MessageResponse])
async def get_conversation(
    request: ConversationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversation history between two peers

    Retrieves encrypted messages exchanged between two peers,
    ordered chronologically (oldest first).

    Args:
        request: Conversation request
        db: Database session

    Returns:
        List of messages
    """
    messages = await bitchat_service.get_conversation(
        peer_id=request.peer_id,
        other_peer_id=request.other_peer_id,
        limit=request.limit,
        offset=request.offset,
        db=db
    )
    return messages


@router.get("/messages/conversation/{peer_id}/{other_peer_id}", response_model=List[MessageResponse])
async def get_conversation_get(
    peer_id: str,
    other_peer_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversation history (GET method)

    Alternative GET endpoint for conversation retrieval.

    Args:
        peer_id: First peer ID
        other_peer_id: Second peer ID
        limit: Maximum messages to return
        offset: Offset for pagination
        db: Database session

    Returns:
        List of messages
    """
    messages = await bitchat_service.get_conversation(
        peer_id=peer_id,
        other_peer_id=other_peer_id,
        limit=limit,
        offset=offset,
        db=db
    )
    return messages


@router.post("/messages/group", response_model=List[MessageResponse])
async def get_group_messages(
    request: GroupMessagesRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages for a group chat

    Args:
        request: Group messages request
        db: Database session

    Returns:
        List of group messages
    """
    messages = await bitchat_service.get_group_messages(
        group_id=request.group_id,
        limit=request.limit,
        offset=request.offset,
        db=db
    )
    return messages


@router.put("/messages/{message_id}/delivered")
async def mark_message_delivered(
    message_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a message as delivered

    Args:
        message_id: Message identifier
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If message not found
    """
    success = await bitchat_service.mark_delivered(message_id, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )

    return {"message": f"Message {message_id} marked as delivered"}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{peer_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    peer_id: str
):
    """
    WebSocket endpoint for real-time messaging

    Establishes persistent connection for a peer to receive
    messages in real-time. Peer is marked online when connected
    and offline when disconnected.

    Args:
        websocket: WebSocket connection
        peer_id: Peer identifier

    Message Format:
        {
            "type": "message" | "group_message",
            "data": {
                "message_id": "...",
                "from_peer_id": "...",
                "content": "...",
                ...
            }
        }
    """
    await bitchat_service.connect_websocket(peer_id, websocket)

    try:
        while True:
            # Receive messages from client (keep-alive, acks, etc.)
            data = await websocket.receive_json()

            # Handle client messages
            if data.get('type') == 'ping':
                await websocket.send_json({'type': 'pong'})

            elif data.get('type') == 'ack':
                message_id = data.get('message_id')
                if message_id:
                    # Mark message as delivered
                    async for db in get_db():
                        await bitchat_service.mark_delivered(message_id, db)
                        break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for peer: {peer_id}")
    except Exception as e:
        logger.error(f"WebSocket error for peer {peer_id}: {e}")
    finally:
        await bitchat_service.disconnect_websocket(peer_id)


# ============================================================================
# Statistics Endpoint
# ============================================================================

@router.get("/stats", response_model=BitChatStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Get BitChat service statistics

    Returns:
        Service statistics including peer counts, message counts, etc.
    """
    stats = await bitchat_service.get_stats(db=db)
    return stats


# ============================================================================
# Group Chat Endpoints
# ============================================================================

from ..schemas.bitchat import (
    GroupCreateRequest,
    GroupResponse,
    GroupMemberAddRequest,
    GroupMemberResponse,
    GroupMessageSendRequest,
    FileUploadInitRequest,
    FileTransferResponse,
    ChunkStatusResponse
)
from ..services.file_transfer import file_transfer_service


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: GroupCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new group chat

    Args:
        request: Group creation data
        db: Database session

    Returns:
        Created group information
    """
    try:
        group = await bitchat_service.create_group(
            name=request.name,
            description=request.description,
            created_by=request.created_by,
            initial_members=request.initial_members,
            db=db
        )
        return group
    except Exception as e:
        logger.error(f"Group creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create group: {str(e)}"
        )


@router.get("/groups", response_model=List[GroupResponse])
async def list_groups(
    peer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List groups (optionally filtered by peer membership)

    Args:
        peer_id: Optional peer ID to filter by membership
        db: Database session

    Returns:
        List of groups
    """
    groups = await bitchat_service.list_groups(peer_id=peer_id, db=db)
    return groups


@router.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get group information

    Args:
        group_id: Group identifier
        db: Database session

    Returns:
        Group information
    """
    group = await bitchat_service.get_group(group_id=group_id, db=db)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found"
        )

    return group


@router.post("/groups/{group_id}/members", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: str,
    request: GroupMemberAddRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a member to a group

    Args:
        group_id: Group identifier
        request: Member addition data
        db: Database session

    Returns:
        Membership information
    """
    try:
        membership = await bitchat_service.add_group_member(
            group_id=group_id,
            peer_id=request.peer_id,
            role=request.role,
            db=db
        )
        return membership
    except Exception as e:
        logger.error(f"Failed to add member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add member: {str(e)}"
        )


@router.delete("/groups/{group_id}/members/{peer_id}")
async def remove_group_member(
    group_id: str,
    peer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a group

    Args:
        group_id: Group identifier
        peer_id: Peer identifier
        db: Database session

    Returns:
        Success message
    """
    success = await bitchat_service.remove_group_member(
        group_id=group_id,
        peer_id=peer_id,
        db=db
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member {peer_id} not found in group {group_id}"
        )

    return {"message": f"Member {peer_id} removed from group {group_id}"}


@router.get("/groups/{group_id}/members", response_model=List[GroupMemberResponse])
async def list_group_members(
    group_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    List members of a group

    Args:
        group_id: Group identifier
        db: Database session

    Returns:
        List of group members
    """
    members = await bitchat_service.list_group_members(group_id=group_id, db=db)
    return members


@router.post("/groups/{group_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_group_message(
    group_id: str,
    request: GroupMessageSendRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to a group

    Args:
        group_id: Group identifier
        request: Message data
        db: Database session

    Returns:
        Sent message information
    """
    try:
        message = await bitchat_service.send_message(
            from_peer_id=request.from_peer_id,
            to_peer_id=None,
            content=request.content,
            group_id=group_id,
            encryption_algorithm=request.encryption_algorithm,
            nonce=request.nonce,
            db=db
        )
        return message
    except Exception as e:
        logger.error(f"Failed to send group message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/groups/{group_id}/messages", response_model=List[MessageResponse])
async def get_group_messages_get(
    group_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages for a group (GET method)

    Args:
        group_id: Group identifier
        limit: Maximum messages to return
        offset: Offset for pagination
        db: Database session

    Returns:
        List of group messages
    """
    messages = await bitchat_service.get_group_messages(
        group_id=group_id,
        limit=limit,
        offset=offset,
        db=db
    )
    return messages


# ============================================================================
# File Transfer Endpoints
# ============================================================================

from fastapi import UploadFile, File as FastAPIFile, Form


@router.post("/files/upload", response_model=FileTransferResponse, status_code=status.HTTP_201_CREATED)
async def initialize_file_upload(
    request: FileUploadInitRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize a file upload

    Args:
        request: File upload initialization data
        db: Database session

    Returns:
        File transfer information
    """
    try:
        transfer = await file_transfer_service.create_upload(
            filename=request.filename,
            file_size=request.file_size,
            uploaded_by=request.uploaded_by,
            mime_type=request.mime_type,
            db=db
        )
        return transfer
    except Exception as e:
        logger.error(f"Failed to initialize upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize upload: {str(e)}"
        )


@router.post("/files/{file_id}/chunks/{chunk_index}")
async def upload_file_chunk(
    file_id: str,
    chunk_index: int,
    chunk_data: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file chunk

    Args:
        file_id: File identifier
        chunk_index: Chunk index
        chunk_data: Chunk binary data
        db: Database session

    Returns:
        Chunk information
    """
    try:
        # Read chunk data
        data = await chunk_data.read()

        # Upload chunk
        chunk = await file_transfer_service.upload_chunk(
            file_id=file_id,
            chunk_index=chunk_index,
            chunk_data=data,
            db=db
        )

        return chunk
    except Exception as e:
        logger.error(f"Failed to upload chunk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload chunk: {str(e)}"
        )


@router.get("/files/{file_id}/chunks", response_model=List[ChunkStatusResponse])
async def get_chunk_status(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get status of all chunks for a file

    Args:
        file_id: File identifier
        db: Database session

    Returns:
        List of chunk status information
    """
    chunks = await file_transfer_service.get_chunk_status(file_id=file_id, db=db)
    return chunks


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Download a complete file

    Args:
        file_id: File identifier
        db: Database session

    Returns:
        File download
    """
    try:
        from fastapi.responses import FileResponse

        file_path = await file_transfer_service.download_file(
            file_id=file_id,
            db=db
        )

        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {file_id} not found or not complete"
            )

        # Get file transfer info for filename
        progress = await file_transfer_service.get_progress(file_id, db)

        return FileResponse(
            path=str(file_path),
            filename=progress.filename if progress else "download",
            media_type="application/octet-stream"
        )

    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )


@router.get("/files/{file_id}", response_model=FileTransferResponse)
async def get_file_transfer_status(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get file transfer status and progress

    Args:
        file_id: File identifier
        db: Database session

    Returns:
        File transfer information
    """
    progress = await file_transfer_service.get_progress(file_id=file_id, db=db)

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File transfer {file_id} not found"
        )

    return FileTransferResponse(
        id=progress.file_id,
        file_id=progress.file_id,
        filename=progress.filename,
        file_size=progress.total_size,
        mime_type=None,
        chunk_size=file_transfer_service.chunk_size,
        total_chunks=progress.total_chunks,
        uploaded_chunks=progress.uploaded_chunks,
        uploaded_by="",
        status=progress.status,
        progress=progress.progress_percent,
        created_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
        download_sources=progress.download_sources
    )
