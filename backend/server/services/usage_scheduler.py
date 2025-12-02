"""
Usage Scheduler Service
Handles scheduled tasks for usage tracking (daily resets at midnight UTC)
"""
import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_context
from .usage_tracking import usage_tracking_service

logger = logging.getLogger(__name__)


class UsageScheduler:
    """
    Scheduler for usage tracking tasks

    Features:
    - Daily reset at midnight UTC
    - Automatic retry on failure
    - Graceful shutdown
    """

    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the usage scheduler background task"""
        if self.is_running:
            logger.warning("Usage scheduler already running")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Usage scheduler started - daily reset at midnight UTC")

    async def stop(self):
        """Stop the usage scheduler"""
        self.is_running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Usage scheduler stopped")

    async def _scheduler_loop(self):
        """
        Main scheduler loop

        Runs daily at midnight UTC to reset usage counters
        """
        while self.is_running:
            try:
                # Calculate time until next midnight UTC
                now = datetime.now(timezone.utc)
                tomorrow = (now + timedelta(days=1)).date()
                next_midnight = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=timezone.utc)
                sleep_seconds = (next_midnight - now).total_seconds()

                logger.info(
                    f"Next usage reset at {next_midnight.isoformat()}Z "
                    f"(in {sleep_seconds/3600:.1f} hours)"
                )

                # Sleep until midnight
                await asyncio.sleep(sleep_seconds)

                # Perform daily reset
                if self.is_running:
                    await self._perform_daily_reset()

            except asyncio.CancelledError:
                logger.info("Usage scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in usage scheduler loop: {e}")
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)

    async def _perform_daily_reset(self):
        """
        Perform daily usage reset

        This doesn't delete records - new day means new records created on-demand.
        Just logs the transition for monitoring.
        """
        try:
            async with get_db_context() as db:
                record_count = await usage_tracking_service.reset_daily_usage(db)

                logger.info(
                    f"Daily usage reset completed at {datetime.now(timezone.utc).isoformat()}Z - "
                    f"{record_count} records from previous day now historical"
                )

        except Exception as e:
            logger.error(f"Failed to perform daily usage reset: {e}")
            raise

    async def manual_reset(self):
        """
        Manually trigger a usage reset (for testing/admin purposes)

        Returns:
            Number of records processed
        """
        try:
            async with get_db_context() as db:
                record_count = await usage_tracking_service.reset_daily_usage(db)

                logger.info(
                    f"Manual usage reset completed at {datetime.now(timezone.utc).isoformat()}Z - "
                    f"{record_count} records processed"
                )

                return record_count

        except Exception as e:
            logger.error(f"Manual usage reset failed: {e}")
            raise


# Global scheduler instance
usage_scheduler = UsageScheduler()
