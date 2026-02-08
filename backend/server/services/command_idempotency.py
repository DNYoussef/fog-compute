"""
Command Idempotency Service
Prevents duplicate task execution on network retries

PHASE2-TASK-003 (p522): Command Idempotency
- Add unique command_id to task assignments
- Dedupe window tracking
- Prevent duplicate execution on network retries
"""
import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Optional, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class CommandStatus(str, Enum):
    """Status of a command in the idempotency tracker"""
    PENDING = "pending"       # Command received, not yet executed
    EXECUTING = "executing"   # Currently being executed
    COMPLETED = "completed"   # Successfully executed
    FAILED = "failed"         # Execution failed
    EXPIRED = "expired"       # Dedupe window expired


@dataclass
class CommandRecord:
    """Record of a command for idempotency tracking"""
    command_id: str
    device_id: str
    task_type: str
    payload_hash: str
    status: CommandStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    execution_count: int = 0
    result: Optional[Any] = None
    error_message: Optional[str] = None


@dataclass
class IdempotencyCheckResult:
    """Result of idempotency check"""
    is_duplicate: bool
    command_id: str
    original_record: Optional[CommandRecord] = None
    message: str = ""


def generate_command_id() -> str:
    """
    Generate a unique command ID.

    Format: cmd-{timestamp_hex}-{random_hex}
    This ensures time-ordered uniqueness.
    """
    timestamp_hex = hex(int(datetime.now(UTC).timestamp() * 1000))[2:]
    random_hex = uuid4().hex[:8]
    return f"cmd-{timestamp_hex}-{random_hex}"


def hash_payload(payload: dict[str, Any]) -> str:
    """
    Generate hash of command payload for duplicate detection.

    Uses stable JSON serialization to ensure consistent hashing.
    """
    import hashlib
    import json

    # Sort keys for consistent serialization
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


class CommandIdempotencyService:
    """
    Service for ensuring command idempotency in fog compute tasks.

    PHASE2-TASK-003: Prevents duplicate execution on network retries
    by tracking command IDs within a configurable dedupe window.
    """

    def __init__(
        self,
        dedupe_window_seconds: int = 300,  # 5 minute default
        max_cache_size: int = 10000,
        cleanup_interval_seconds: int = 60,
    ):
        """
        Initialize idempotency service.

        Args:
            dedupe_window_seconds: Duration to track command IDs
            max_cache_size: Maximum commands to track
            cleanup_interval_seconds: Interval for cache cleanup
        """
        self.dedupe_window_seconds = dedupe_window_seconds
        self.max_cache_size = max_cache_size
        self.cleanup_interval_seconds = cleanup_interval_seconds

        # Use OrderedDict for LRU-style tracking
        self._commands: OrderedDict[str, CommandRecord] = OrderedDict()
        self._payload_index: dict[str, str] = {}  # payload_hash -> command_id

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Statistics
        self._stats = {
            "total_commands": 0,
            "duplicates_prevented": 0,
            "expirations": 0,
        }

        logger.info(
            f"CommandIdempotencyService initialized: "
            f"window={dedupe_window_seconds}s, max_size={max_cache_size}"
        )

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._is_running:
            return

        self._is_running = True

        async def cleanup_loop():
            while self._is_running:
                await asyncio.sleep(self.cleanup_interval_seconds)
                self._cleanup_expired()

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Command idempotency cleanup started")

    async def stop(self) -> None:
        """Stop background cleanup task."""
        self._is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Command idempotency cleanup stopped")

    def _cleanup_expired(self) -> None:
        """Remove expired command records."""
        now = datetime.now(UTC)
        expired_ids = []

        for command_id, record in self._commands.items():
            if record.expires_at <= now:
                expired_ids.append(command_id)

        for command_id in expired_ids:
            record = self._commands.pop(command_id, None)
            if record:
                self._payload_index.pop(record.payload_hash, None)
                self._stats["expirations"] += 1

        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired commands")

    def _enforce_size_limit(self) -> None:
        """Enforce max cache size by removing oldest entries."""
        while len(self._commands) >= self.max_cache_size:
            # Remove oldest (first) entry
            command_id, record = self._commands.popitem(last=False)
            self._payload_index.pop(record.payload_hash, None)
            logger.debug(f"Evicted command {command_id} due to size limit")

    def register_command(
        self,
        device_id: str,
        task_type: str,
        payload: dict[str, Any],
        command_id: Optional[str] = None,
    ) -> tuple[str, IdempotencyCheckResult]:
        """
        Register a new command and check for duplicates.

        PHASE2-TASK-003: Main entry point for command registration.

        Args:
            device_id: Device sending the command
            task_type: Type of task
            payload: Command payload
            command_id: Optional pre-generated command ID

        Returns:
            Tuple of (command_id, check_result)
        """
        now = datetime.now(UTC)
        payload_hash = hash_payload(payload)

        # Check for duplicate by command_id
        if command_id and command_id in self._commands:
            original = self._commands[command_id]
            self._stats["duplicates_prevented"] += 1

            return command_id, IdempotencyCheckResult(
                is_duplicate=True,
                command_id=command_id,
                original_record=original,
                message=f"Duplicate command_id: {command_id}, original status: {original.status.value}"
            )

        # Check for duplicate by payload hash
        existing_id = self._payload_index.get(payload_hash)
        if existing_id and existing_id in self._commands:
            original = self._commands[existing_id]

            # Only consider it duplicate if within dedupe window
            if original.expires_at > now:
                self._stats["duplicates_prevented"] += 1

                return existing_id, IdempotencyCheckResult(
                    is_duplicate=True,
                    command_id=existing_id,
                    original_record=original,
                    message=f"Duplicate payload detected, original command: {existing_id}"
                )

        # Generate new command_id if not provided
        if not command_id:
            command_id = generate_command_id()

        # Enforce size limit before adding
        self._enforce_size_limit()

        # Create new record
        expires_at = now + timedelta(seconds=self.dedupe_window_seconds)
        record = CommandRecord(
            command_id=command_id,
            device_id=device_id,
            task_type=task_type,
            payload_hash=payload_hash,
            status=CommandStatus.PENDING,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

        # Store in both indices
        self._commands[command_id] = record
        self._payload_index[payload_hash] = command_id
        self._stats["total_commands"] += 1

        return command_id, IdempotencyCheckResult(
            is_duplicate=False,
            command_id=command_id,
            message="New command registered"
        )

    def check_duplicate(
        self,
        command_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> IdempotencyCheckResult:
        """
        Check if a command is a duplicate.

        PHASE2-TASK-003: Check-only operation for validation.

        Args:
            command_id: Command ID to check
            payload: Payload to check (hash-based)

        Returns:
            Check result
        """
        now = datetime.now(UTC)

        # Check by command_id
        if command_id:
            record = self._commands.get(command_id)
            if record and record.expires_at > now:
                return IdempotencyCheckResult(
                    is_duplicate=True,
                    command_id=command_id,
                    original_record=record,
                    message=f"Command {command_id} already registered"
                )

        # Check by payload hash
        if payload:
            payload_hash = hash_payload(payload)
            existing_id = self._payload_index.get(payload_hash)
            if existing_id:
                record = self._commands.get(existing_id)
                if record and record.expires_at > now:
                    return IdempotencyCheckResult(
                        is_duplicate=True,
                        command_id=existing_id,
                        original_record=record,
                        message=f"Payload matches existing command {existing_id}"
                    )

        return IdempotencyCheckResult(
            is_duplicate=False,
            command_id=command_id or "",
            message="No duplicate found"
        )

    def update_status(
        self,
        command_id: str,
        status: CommandStatus,
        result: Optional[Any] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update command status.

        PHASE2-TASK-003: Track execution state for idempotency.

        Args:
            command_id: Command to update
            status: New status
            result: Optional result data
            error_message: Optional error message

        Returns:
            True if updated
        """
        record = self._commands.get(command_id)
        if not record:
            return False

        record.status = status
        record.updated_at = datetime.now(UTC)
        record.execution_count += 1

        if result is not None:
            record.result = result
        if error_message:
            record.error_message = error_message

        # Move to end for LRU behavior
        self._commands.move_to_end(command_id)

        logger.debug(f"Command {command_id} status updated to {status.value}")
        return True

    def mark_executing(self, command_id: str) -> bool:
        """Mark command as currently executing."""
        return self.update_status(command_id, CommandStatus.EXECUTING)

    def mark_completed(self, command_id: str, result: Any = None) -> bool:
        """Mark command as successfully completed."""
        return self.update_status(command_id, CommandStatus.COMPLETED, result=result)

    def mark_failed(self, command_id: str, error_message: str) -> bool:
        """Mark command as failed."""
        return self.update_status(
            command_id,
            CommandStatus.FAILED,
            error_message=error_message
        )

    def get_command(self, command_id: str) -> Optional[CommandRecord]:
        """Get command record by ID."""
        return self._commands.get(command_id)

    def get_command_result(self, command_id: str) -> Optional[Any]:
        """
        Get cached result for a command.

        PHASE2-TASK-003: Return cached result for duplicate requests.
        """
        record = self._commands.get(command_id)
        if record and record.status == CommandStatus.COMPLETED:
            return record.result
        return None

    def extend_dedupe_window(
        self,
        command_id: str,
        additional_seconds: int
    ) -> bool:
        """
        Extend the dedupe window for a command.

        Useful for long-running tasks that need protection
        beyond the default window.

        Args:
            command_id: Command to extend
            additional_seconds: Seconds to add

        Returns:
            True if extended
        """
        record = self._commands.get(command_id)
        if not record:
            return False

        record.expires_at += timedelta(seconds=additional_seconds)
        record.updated_at = datetime.now(UTC)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "active_commands": len(self._commands),
            "total_commands": self._stats["total_commands"],
            "duplicates_prevented": self._stats["duplicates_prevented"],
            "expirations": self._stats["expirations"],
            "dedupe_window_seconds": self.dedupe_window_seconds,
            "max_cache_size": self.max_cache_size,
        }


# Global instance
_idempotency_service: Optional[CommandIdempotencyService] = None


def get_command_idempotency_service() -> CommandIdempotencyService:
    """Get or create the command idempotency service instance."""
    global _idempotency_service

    if _idempotency_service is None:
        _idempotency_service = CommandIdempotencyService()

    return _idempotency_service
