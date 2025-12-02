"""
BitChat Group Management Extension
Extends BitChat service with group chat functionality
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging
import uuid
import hashlib

from ..models.database import GroupChat, GroupMembership, Peer

logger = logging.getLogger(__name__)


async def create_group(
    name: str,
    description: Optional[str],
    created_by: str,
    initial_members: List[str],
    db: AsyncSession
) -> Dict:
    """
    Create a new group chat

    Args:
        name: Group name
        description: Optional group description
        created_by: Creator peer ID
        initial_members: List of initial member peer IDs
        db: Database session

    Returns:
        Group dictionary
    """
    try:
        # Generate group ID
        group_id = _generate_group_id(name, created_by)

        # Create group
        group = GroupChat(
            group_id=group_id,
            name=name,
            description=description,
            created_by=created_by,
            member_count=1 + len(initial_members)
        )

        db.add(group)

        # Add creator as admin
        creator_membership = GroupMembership(
            group_id=group_id,
            peer_id=created_by,
            role='admin'
        )
        db.add(creator_membership)

        # Add initial members
        for peer_id in initial_members:
            if peer_id != created_by:
                membership = GroupMembership(
                    group_id=group_id,
                    peer_id=peer_id,
                    role='member'
                )
                db.add(membership)

        await db.commit()
        await db.refresh(group)

        logger.info(f"Created group {group_id}: {name} with {len(initial_members) + 1} members")
        return group.to_dict()

    except Exception as e:
        logger.error(f"Error creating group: {e}")
        await db.rollback()
        raise


async def list_groups(
    peer_id: Optional[str],
    db: AsyncSession
) -> List[Dict]:
    """
    List groups (optionally filtered by peer membership)

    Args:
        peer_id: Optional peer ID to filter by
        db: Database session

    Returns:
        List of group dictionaries
    """
    try:
        if peer_id:
            # Get groups where peer is a member
            query = (
                select(GroupChat)
                .join(GroupMembership)
                .where(
                    and_(
                        GroupMembership.peer_id == peer_id,
                        GroupMembership.is_active == True,
                        GroupChat.is_active == True
                    )
                )
            )
        else:
            # Get all active groups
            query = select(GroupChat).where(GroupChat.is_active == True)

        result = await db.execute(query)
        groups = result.scalars().all()

        return [group.to_dict() for group in groups]

    except Exception as e:
        logger.error(f"Error listing groups: {e}")
        return []


async def get_group(
    group_id: str,
    db: AsyncSession
) -> Optional[Dict]:
    """
    Get group information

    Args:
        group_id: Group identifier
        db: Database session

    Returns:
        Group dictionary or None
    """
    try:
        result = await db.execute(
            select(GroupChat).where(GroupChat.group_id == group_id)
        )
        group = result.scalar_one_or_none()

        return group.to_dict() if group else None

    except Exception as e:
        logger.error(f"Error getting group: {e}")
        return None


async def add_group_member(
    group_id: str,
    peer_id: str,
    role: str,
    db: AsyncSession
) -> Dict:
    """
    Add a member to a group

    Args:
        group_id: Group identifier
        peer_id: Peer identifier to add
        role: Member role
        db: Database session

    Returns:
        Membership dictionary
    """
    try:
        # Check if already a member
        existing_result = await db.execute(
            select(GroupMembership).where(
                and_(
                    GroupMembership.group_id == group_id,
                    GroupMembership.peer_id == peer_id
                )
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if existing.is_active:
                logger.warning(f"Peer {peer_id} already a member of group {group_id}")
                return existing.to_dict()
            else:
                # Reactivate membership
                existing.is_active = True
                existing.role = role
                existing.left_at = None
                await db.commit()
                await db.refresh(existing)
                return existing.to_dict()

        # Create membership
        membership = GroupMembership(
            group_id=group_id,
            peer_id=peer_id,
            role=role
        )

        db.add(membership)

        # Update group member count
        group_result = await db.execute(
            select(GroupChat).where(GroupChat.group_id == group_id)
        )
        group = group_result.scalar_one_or_none()

        if group:
            group.member_count += 1

        await db.commit()
        await db.refresh(membership)

        logger.info(f"Added {peer_id} to group {group_id} as {role}")
        return membership.to_dict()

    except Exception as e:
        logger.error(f"Error adding group member: {e}")
        await db.rollback()
        raise


async def remove_group_member(
    group_id: str,
    peer_id: str,
    db: AsyncSession
) -> bool:
    """
    Remove a member from a group

    Args:
        group_id: Group identifier
        peer_id: Peer identifier to remove
        db: Database session

    Returns:
        Success status
    """
    try:
        result = await db.execute(
            select(GroupMembership).where(
                and_(
                    GroupMembership.group_id == group_id,
                    GroupMembership.peer_id == peer_id,
                    GroupMembership.is_active == True
                )
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            return False

        # Mark as inactive
        membership.is_active = False
        membership.left_at = datetime.now(timezone.utc)

        # Update group member count
        group_result = await db.execute(
            select(GroupChat).where(GroupChat.group_id == group_id)
        )
        group = group_result.scalar_one_or_none()

        if group:
            group.member_count = max(0, group.member_count - 1)

        await db.commit()

        logger.info(f"Removed {peer_id} from group {group_id}")
        return True

    except Exception as e:
        logger.error(f"Error removing group member: {e}")
        await db.rollback()
        return False


async def list_group_members(
    group_id: str,
    db: AsyncSession
) -> List[Dict]:
    """
    List members of a group

    Args:
        group_id: Group identifier
        db: Database session

    Returns:
        List of membership dictionaries
    """
    try:
        result = await db.execute(
            select(GroupMembership).where(
                and_(
                    GroupMembership.group_id == group_id,
                    GroupMembership.is_active == True
                )
            )
        )
        memberships = result.scalars().all()

        return [membership.to_dict() for membership in memberships]

    except Exception as e:
        logger.error(f"Error listing group members: {e}")
        return []


def _generate_group_id(name: str, created_by: str) -> str:
    """Generate unique group ID"""
    data = f"{name}:{created_by}:{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]
