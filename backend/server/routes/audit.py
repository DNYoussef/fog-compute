"""
Audit Log API Routes
Query audit logs with admin-only access
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime
from typing import Optional, List
import logging

from ..database import get_db
from ..models.database import User
from ..models.audit_log import AuditLog
from ..auth.dependencies import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency to require admin privileges

    Args:
        current_user: Currently authenticated user

    Returns:
        User object if admin

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


@router.get("/logs", response_model=dict)
async def get_audit_logs(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),

    # Filters
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    status: Optional[str] = Query(None, description="Filter by status (success/failure/denied)"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),

    # Date range
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),

    # Sorting
    sort_by: str = Query("timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),

    # Dependencies
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Query audit logs with filtering and pagination

    **Admin Only**

    **Query Parameters:**
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 1000)
    - event_type: Filter by event type
    - user_id: Filter by user ID
    - resource_type: Filter by resource type (user, job, node, etc.)
    - resource_id: Filter by resource ID
    - status: Filter by status (success, failure, denied)
    - ip_address: Filter by IP address
    - correlation_id: Filter by correlation ID
    - start_date: Start date filter (ISO 8601)
    - end_date: End date filter (ISO 8601)
    - sort_by: Field to sort by (default: timestamp)
    - sort_order: Sort order - asc or desc (default: desc)

    **Returns:**
    - logs: List of audit log entries
    - total: Total number of matching logs
    - page: Current page number
    - page_size: Items per page
    - total_pages: Total number of pages
    """

    # Build base query
    query = select(AuditLog)
    filters = []

    # Apply filters
    if event_type:
        filters.append(AuditLog.event_type == event_type)

    if user_id:
        filters.append(AuditLog.user_id == user_id)

    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)

    if resource_id:
        filters.append(AuditLog.resource_id == resource_id)

    if status:
        filters.append(AuditLog.status == status)

    if ip_address:
        filters.append(AuditLog.ip_address == ip_address)

    if correlation_id:
        filters.append(AuditLog.correlation_id == correlation_id)

    if start_date:
        filters.append(AuditLog.timestamp >= start_date)

    if end_date:
        filters.append(AuditLog.timestamp <= end_date)

    if filters:
        query = query.where(and_(*filters))

    # Get total count
    count_query = select(func.count()).select_from(AuditLog)
    if filters:
        count_query = count_query.where(and_(*filters))

    result = await db.execute(count_query)
    total = result.scalar()

    # Apply sorting
    sort_column = getattr(AuditLog, sort_by, AuditLog.timestamp)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()

    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size

    return {
        "logs": [log.to_dict() for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/logs/{log_id}", response_model=dict)
async def get_audit_log_by_id(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Get a specific audit log entry by ID

    **Admin Only**

    **Path Parameters:**
    - log_id: UUID of the audit log entry

    **Returns:**
    - Audit log entry details
    """
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found"
        )

    return log.to_dict()


@router.get("/stats", response_model=dict)
async def get_audit_stats(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Get audit log statistics

    **Admin Only**

    **Query Parameters:**
    - start_date: Start date filter (ISO 8601)
    - end_date: End date filter (ISO 8601)

    **Returns:**
    - total_events: Total number of audit events
    - event_type_breakdown: Count by event type
    - status_breakdown: Count by status
    - top_users: Most active users
    - top_ips: Most active IP addresses
    """

    # Build base query filters
    filters = []
    if start_date:
        filters.append(AuditLog.timestamp >= start_date)
    if end_date:
        filters.append(AuditLog.timestamp <= end_date)

    # Total events
    count_query = select(func.count()).select_from(AuditLog)
    if filters:
        count_query = count_query.where(and_(*filters))

    result = await db.execute(count_query)
    total_events = result.scalar()

    # Event type breakdown
    event_type_query = (
        select(AuditLog.event_type, func.count(AuditLog.id).label('count'))
        .group_by(AuditLog.event_type)
        .order_by(func.count(AuditLog.id).desc())
    )
    if filters:
        event_type_query = event_type_query.where(and_(*filters))

    result = await db.execute(event_type_query)
    event_type_breakdown = {row[0]: row[1] for row in result.all()}

    # Status breakdown
    status_query = (
        select(AuditLog.status, func.count(AuditLog.id).label('count'))
        .group_by(AuditLog.status)
        .order_by(func.count(AuditLog.id).desc())
    )
    if filters:
        status_query = status_query.where(and_(*filters))

    result = await db.execute(status_query)
    status_breakdown = {row[0]: row[1] for row in result.all()}

    # Top users (exclude null user_id)
    user_query = (
        select(AuditLog.user_id, func.count(AuditLog.id).label('count'))
        .where(AuditLog.user_id.isnot(None))
        .group_by(AuditLog.user_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )
    if filters:
        user_query = user_query.where(and_(*filters))

    result = await db.execute(user_query)
    top_users = [{"user_id": str(row[0]), "count": row[1]} for row in result.all()]

    # Top IPs
    ip_query = (
        select(AuditLog.ip_address, func.count(AuditLog.id).label('count'))
        .group_by(AuditLog.ip_address)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )
    if filters:
        ip_query = ip_query.where(and_(*filters))

    result = await db.execute(ip_query)
    top_ips = [{"ip": row[0], "count": row[1]} for row in result.all()]

    return {
        "total_events": total_events,
        "event_type_breakdown": event_type_breakdown,
        "status_breakdown": status_breakdown,
        "top_users": top_users,
        "top_ips": top_ips,
    }
