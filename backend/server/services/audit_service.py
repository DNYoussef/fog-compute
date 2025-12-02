"""
Audit Service
Provides async audit logging with batch writes for performance
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from ..models.audit_log import AuditLog
from ..database import get_db_context

logger = logging.getLogger(__name__)


class AuditService:
    """
    Audit Logging Service
    Manages audit log entries with batching for performance
    """

    def __init__(self, batch_size: int = 10, flush_interval: float = 5.0):
        """
        Initialize audit service

        Args:
            batch_size: Number of logs to batch before writing
            flush_interval: Seconds between forced flushes
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batch: List[AuditLog] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background flush task"""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._periodic_flush())
            logger.info(f"Audit service started (batch_size={self.batch_size}, flush_interval={self.flush_interval}s)")

    async def stop(self):
        """Stop the background flush task and flush remaining logs"""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Flush any remaining logs
        await self.flush()
        logger.info("Audit service stopped")

    async def log_event(
        self,
        action: str,
        ip_address: str,
        user_id: Optional[UUID] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        response_status: Optional[int] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log an audit event (async, batched)

        Args:
            action: Action performed (login, logout, deploy, delete, create, read, update, etc.)
            ip_address: Client IP address
            user_id: Optional user ID (nullable for anonymous/system events)
            user_agent: Optional user agent string
            resource_type: Optional resource type (deployment, user, node, job, etc.)
            resource_id: Optional resource UUID
            correlation_id: Optional correlation UUID for request tracing
            request_method: Optional HTTP method (GET, POST, PUT, DELETE, PATCH)
            request_path: Optional HTTP request path
            response_status: Optional HTTP response status code
            duration_ms: Optional request duration in milliseconds
            metadata: Optional additional flexible context (JSONB)
                     Can include: event_type, old_value, new_value, error_message,
                                 session_id, api_key_id, custom fields, etc.
        """
        log_entry = AuditLog(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            request_method=request_method,
            request_path=request_path,
            response_status=response_status,
            duration_ms=duration_ms,
            context=metadata,  # Maps to 'metadata' column in database
        )

        async with self._lock:
            self._batch.append(log_entry)

            # Flush if batch is full
            if len(self._batch) >= self.batch_size:
                await self._flush_batch()

    async def flush(self):
        """Force flush all pending logs"""
        async with self._lock:
            await self._flush_batch()

    async def _flush_batch(self):
        """Internal: Flush current batch to database"""
        if not self._batch:
            return

        try:
            async with get_db_context() as db:
                db.add_all(self._batch)
                await db.commit()
                logger.debug(f"Flushed {len(self._batch)} audit log entries")
                self._batch.clear()
        except Exception as e:
            logger.error(f"Failed to flush audit logs: {e}")
            # Keep logs in batch for retry
            raise

    async def _periodic_flush(self):
        """Background task: Periodically flush logs"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")


# Singleton instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get or create the global audit service instance"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service


async def log_audit_event(
    action: str,
    ip_address: str,
    user_id: Optional[UUID] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    correlation_id: Optional[UUID] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    response_status: Optional[int] = None,
    duration_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Convenience function to log an audit event
    Uses the global audit service instance
    """
    service = get_audit_service()
    await service.log_event(
        action=action,
        ip_address=ip_address,
        user_id=user_id,
        user_agent=user_agent,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=correlation_id,
        request_method=request_method,
        request_path=request_path,
        response_status=response_status,
        duration_ms=duration_ms,
        metadata=metadata,
    )
