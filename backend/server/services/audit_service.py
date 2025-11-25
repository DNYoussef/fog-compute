"""
Audit Service
Provides async audit logging with batch writes for performance
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
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
        event_type: str,
        ip_address: str,
        action: str,
        status: str,
        user_id: Optional[UUID] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log an audit event (async, batched)

        Args:
            event_type: Type of event (login, data_access, admin_action, etc.)
            ip_address: Client IP address
            action: Action performed (create, read, update, delete, etc.)
            status: Outcome (success, failure, denied)
            user_id: Optional user ID
            user_agent: Optional user agent string
            resource_type: Optional resource type (user, job, node, etc.)
            resource_id: Optional resource ID
            old_value: Optional previous state (for updates)
            new_value: Optional new state (for updates)
            correlation_id: Optional correlation ID for request tracing
            metadata: Optional additional context
        """
        log_entry = AuditLog(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            status=status,
            correlation_id=correlation_id,
            metadata=metadata,
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
    event_type: str,
    ip_address: str,
    action: str,
    status: str,
    user_id: Optional[UUID] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Convenience function to log an audit event
    Uses the global audit service instance
    """
    service = get_audit_service()
    await service.log_event(
        event_type=event_type,
        ip_address=ip_address,
        action=action,
        status=status,
        user_id=user_id,
        user_agent=user_agent,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        correlation_id=correlation_id,
        metadata=metadata,
    )
