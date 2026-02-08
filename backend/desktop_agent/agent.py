"""
Desktop Agent Main Module
Cross-platform desktop agent for fog computing mesh

PHASE3-AGENT-001: Cross-Platform Compatibility
- Works on Windows, macOS, Linux
- Uses pathlib for paths
- PyInstaller-compatible structure
- Platform-specific install scripts
"""
import asyncio
import logging
import platform
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Callable, Awaitable

from .config import AgentConfig, ensure_directories, get_platform
from .discovery import CoordinatorDiscovery, CoordinatorInfo, DiscoveryMethod
from .executor import TaskExecutor, TaskAssignment, ExecutionResult, ExecutionStatus
from .resource_monitor import ResourceMonitor, ResourceStatus, ResourceThresholds, ResourceMetrics

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent lifecycle status"""
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    REGISTERING = "registering"
    ACTIVE = "active"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    ERROR = "error"


class DesktopAgent:
    """
    Main desktop agent for fog computing mesh.

    PHASE3-AGENT-001: Cross-platform desktop agent.

    Integrates:
    - PHASE3-AGENT-002: Sandboxed Task Execution (TaskExecutor)
    - PHASE3-AGENT-003: Auto-Discovery + Manual Fallback (CoordinatorDiscovery)
    - PHASE3-AGENT-004: Resource Limits Enforcement (ResourceMonitor)
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize desktop agent.

        Args:
            config: Agent configuration (loads from file if None)
        """
        self.config = config or AgentConfig.load()
        self._status = AgentStatus.INITIALIZING

        # Ensure directories exist
        ensure_directories(self.config)

        # Initialize components
        self._discovery = CoordinatorDiscovery(
            service_name=self.config.discovery_service_name,
            default_port=self.config.coordinator_port,
            manual_url=self.config.coordinator_url,
            tls_enabled=self.config.tls_enabled,
            discovery_timeout_sec=self.config.discovery_timeout_sec,
            max_retries=self.config.max_retries,
            base_delay_sec=self.config.retry_base_delay_sec,
            max_delay_sec=self.config.retry_max_delay_sec,
        )

        self._resource_monitor = ResourceMonitor(
            thresholds=ResourceThresholds(
                cpu_overloaded=self.config.max_cpu_percent,
                memory_overloaded=self.config.max_memory_percent,
            ),
            on_status_change=self._on_resource_status_change,
        )

        self._executor = TaskExecutor(
            allowed_task_types=self.config.task_types,
            max_concurrent_tasks=self.config.max_concurrent_tasks,
            on_task_complete=self._on_task_complete,
        )

        # Runtime state
        self._coordinator: Optional[CoordinatorInfo] = None
        self._auth_token: Optional[str] = self.config.auth_token
        self._registered = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._task_polling_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Callbacks
        self._on_status_change: Optional[Callable[[AgentStatus, AgentStatus], Awaitable[None]]] = None

        logger.info(
            f"DesktopAgent initialized: "
            f"device_id={self.config.device_id}, "
            f"platform={get_platform()}, "
            f"task_types={self.config.task_types}"
        )

    def set_status_callback(
        self,
        callback: Callable[[AgentStatus, AgentStatus], Awaitable[None]]
    ) -> None:
        """Set callback for status changes."""
        self._on_status_change = callback

    async def _set_status(self, new_status: AgentStatus) -> None:
        """Update agent status and trigger callback."""
        old_status = self._status
        self._status = new_status

        logger.info(f"Agent status: {old_status.value} -> {new_status.value}")

        if self._on_status_change:
            try:
                await self._on_status_change(old_status, new_status)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")

    async def start(self) -> bool:
        """
        Start the desktop agent.

        PHASE3-AGENT-001: Main agent startup sequence.

        Returns:
            True if started successfully
        """
        try:
            await self._set_status(AgentStatus.INITIALIZING)

            # Start resource monitoring (PHASE3-AGENT-004)
            await self._resource_monitor.start()

            # Discover coordinator (PHASE3-AGENT-003)
            await self._set_status(AgentStatus.DISCOVERING)
            self._coordinator = await self._discovery.discover()

            if not self._coordinator:
                logger.error("Failed to discover coordinator")
                await self._set_status(AgentStatus.ERROR)
                return False

            # Verify coordinator is reachable
            await self._set_status(AgentStatus.CONNECTING)
            if not await self._discovery.verify_coordinator(self._coordinator):
                logger.error("Coordinator not reachable")
                await self._set_status(AgentStatus.DISCONNECTED)
                return False

            # Set callback URL for executor
            self._executor.callback_url = self._coordinator.url

            # Register with coordinator
            await self._set_status(AgentStatus.REGISTERING)
            if not await self._register():
                logger.error("Failed to register with coordinator")
                await self._set_status(AgentStatus.ERROR)
                return False

            # Start background tasks
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._task_polling_task = asyncio.create_task(self._task_polling_loop())

            await self._set_status(AgentStatus.ACTIVE)
            logger.info("Desktop agent started successfully")

            return True

        except Exception as e:
            logger.error(f"Agent start error: {e}")
            await self._set_status(AgentStatus.ERROR)
            return False

    async def stop(self) -> None:
        """
        Stop the desktop agent gracefully.

        PHASE3-AGENT-001: Graceful shutdown.
        """
        await self._set_status(AgentStatus.SHUTTING_DOWN)

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel background tasks
        for task in [self._heartbeat_task, self._task_polling_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Cancel running executions
        await self._executor.cancel_all()

        # Stop resource monitoring
        await self._resource_monitor.stop()

        # Close discovery
        await self._discovery.close()

        # Deregister from coordinator
        await self._deregister()

        await self._set_status(AgentStatus.STOPPED)
        logger.info("Desktop agent stopped")

    async def run(self) -> None:
        """
        Run agent until shutdown.

        PHASE3-AGENT-001: Main run loop.
        """
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

        if not await self.start():
            return

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        await self.stop()

    def _setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.

        PHASE3-AGENT-001: Cross-platform signal handling.
        """
        def handle_signal(sig):
            logger.info(f"Received signal {sig}, initiating shutdown")
            self._shutdown_event.set()

        # Different handling for Windows vs Unix
        if platform.system() == "Windows":
            # Windows: can only handle SIGINT and SIGTERM
            try:
                signal.signal(signal.SIGINT, lambda s, f: handle_signal(s))
                signal.signal(signal.SIGTERM, lambda s, f: handle_signal(s))
            except Exception as e:
                logger.warning(f"Could not set signal handlers: {e}")
        else:
            # Unix: use asyncio signal handling
            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
            except Exception as e:
                logger.warning(f"Could not set signal handlers: {e}")

    async def _register(self) -> bool:
        """
        Register with coordinator.

        Returns:
            True if registered successfully
        """
        if not self._coordinator:
            return False

        try:
            import aiohttp

            # Build registration payload
            metrics = self._resource_monitor.get_current_metrics()

            payload = {
                "device_id": self.config.device_id,
                "device_name": self.config.device_name,
                "task_types": self.config.task_types,
                "max_concurrent_tasks": self.config.max_concurrent_tasks,
                "platform": get_platform(),
                "cpu_cores": metrics.cpu_count,
                "memory_total_mb": metrics.memory_total_mb,
                "enrollment_code": self.config.enrollment_code,
            }

            # Include auth token if available
            headers = {}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"

            url = f"{self._coordinator.url}/api/mesh/register"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=self.config.tls_verify,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._auth_token = data.get("token")
                        self._registered = True

                        # Save token to config
                        self.config.auth_token = self._auth_token
                        self.config.save()

                        logger.info("Registered with coordinator successfully")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Registration failed: {response.status} - {error}")
                        return False

        except ImportError:
            logger.error("aiohttp not installed - cannot register")
            return False
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False

    async def _deregister(self) -> None:
        """Deregister from coordinator."""
        if not self._coordinator or not self._registered:
            return

        try:
            import aiohttp

            headers = {}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"

            url = f"{self._coordinator.url}/api/mesh/deregister"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"device_id": self.config.device_id},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=self.config.tls_verify,
                ) as response:
                    if response.status == 200:
                        logger.info("Deregistered from coordinator")
                    else:
                        logger.warning(f"Deregistration failed: {response.status}")

        except Exception as e:
            logger.warning(f"Deregistration error: {e}")

    async def _heartbeat_loop(self) -> None:
        """
        Background heartbeat loop.

        PHASE3-AGENT-004: Report metrics in heartbeat.
        """
        while not self._shutdown_event.is_set():
            try:
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(self.config.heartbeat_interval_sec)

    async def _send_heartbeat(self) -> bool:
        """Send heartbeat to coordinator."""
        if not self._coordinator or not self._auth_token:
            return False

        try:
            import aiohttp

            # Get current metrics (PHASE3-AGENT-004)
            metrics = self._resource_monitor.get_current_metrics()

            payload = {
                "device_id": self.config.device_id,
                "status": self._status.value,
                "resource_status": metrics.status.value,
                "metrics": metrics.to_dict(),
                "active_tasks": self._executor.get_active_executions(),
                "can_accept_tasks": self._resource_monitor.can_accept_task(),
            }

            headers = {"Authorization": f"Bearer {self._auth_token}"}
            url = f"{self._coordinator.url}/api/mesh/heartbeat"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.heartbeat_timeout_sec),
                    ssl=self.config.tls_verify,
                ) as response:
                    if response.status == 200:
                        logger.debug("Heartbeat sent successfully")
                        return True
                    else:
                        logger.warning(f"Heartbeat failed: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return False

    async def _task_polling_loop(self) -> None:
        """
        Background task polling loop.

        Polls coordinator for assigned tasks.
        """
        while not self._shutdown_event.is_set():
            try:
                # Only poll if we can accept tasks
                if self._resource_monitor.can_accept_task():
                    await self._poll_for_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task polling error: {e}")

            # Poll less frequently than heartbeat
            await asyncio.sleep(self.config.heartbeat_interval_sec / 2)

    async def _poll_for_tasks(self) -> None:
        """Poll coordinator for pending tasks."""
        if not self._coordinator or not self._auth_token:
            return

        try:
            import aiohttp

            headers = {"Authorization": f"Bearer {self._auth_token}"}
            url = f"{self._coordinator.url}/api/mesh/tasks/{self.config.device_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=self.config.tls_verify,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        tasks = data.get("tasks", [])

                        for task_data in tasks:
                            # Create task assignment
                            task = TaskAssignment(
                                command_id=task_data["command_id"],
                                task_type=task_data["task_type"],
                                command=task_data["command"],
                                input_data=task_data.get("input_data"),
                                env=task_data.get("env"),
                                timeout_sec=task_data.get("timeout_sec"),
                            )

                            # Execute task
                            asyncio.create_task(self._execute_task(task))

        except Exception as e:
            logger.debug(f"Task polling error: {e}")

    async def _execute_task(self, task: TaskAssignment) -> None:
        """Execute a task and report result."""
        # Update resource monitor
        self._resource_monitor.increment_active_tasks()

        try:
            result = await self._executor.execute_task(task)
            await self._report_result(result)
        finally:
            self._resource_monitor.decrement_active_tasks()

    async def _report_result(self, result: ExecutionResult) -> None:
        """Report task result to coordinator."""
        if not self._coordinator or not self._auth_token:
            return

        try:
            import aiohttp

            headers = {"Authorization": f"Bearer {self._auth_token}"}
            url = f"{self._coordinator.url}/api/mesh/tasks/result"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=result.to_dict(),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=self.config.tls_verify,
                ) as response:
                    if response.status == 200:
                        logger.info(f"Result reported for {result.command_id}")
                    else:
                        logger.warning(f"Result report failed: {response.status}")

        except Exception as e:
            logger.error(f"Result report error: {e}")

    async def _on_task_complete(self, result: ExecutionResult) -> None:
        """Callback when task completes."""
        logger.info(
            f"Task {result.command_id} completed: "
            f"status={result.status.value}, "
            f"duration={result.duration_ms}ms"
        )

    async def _on_resource_status_change(
        self,
        old_status: ResourceStatus,
        new_status: ResourceStatus
    ) -> None:
        """
        Callback when resource status changes.

        PHASE3-AGENT-004: Pause accepting if overloaded.
        """
        if new_status == ResourceStatus.OVERLOADED:
            if self.config.pause_on_overload:
                logger.warning("Resources overloaded, pausing task acceptance")
                await self._set_status(AgentStatus.PAUSED)

        elif old_status == ResourceStatus.OVERLOADED and new_status in (
            ResourceStatus.AVAILABLE,
            ResourceStatus.LIMITED
        ):
            if self._status == AgentStatus.PAUSED:
                logger.info("Resources recovered, resuming task acceptance")
                await self._set_status(AgentStatus.ACTIVE)

    @property
    def status(self) -> AgentStatus:
        """Get current agent status."""
        return self._status

    @property
    def device_id(self) -> str:
        """Get device ID."""
        return self.config.device_id

    @property
    def is_active(self) -> bool:
        """Check if agent is active."""
        return self._status == AgentStatus.ACTIVE

    def get_info(self) -> dict[str, Any]:
        """Get agent information."""
        metrics = self._resource_monitor.get_current_metrics()

        return {
            "device_id": self.config.device_id,
            "device_name": self.config.device_name,
            "status": self._status.value,
            "platform": get_platform(),
            "coordinator": self._coordinator.to_dict() if self._coordinator else None,
            "registered": self._registered,
            "task_types": self.config.task_types,
            "max_concurrent_tasks": self.config.max_concurrent_tasks,
            "resource_metrics": metrics.to_dict(),
            "executor_stats": self._executor.get_stats(),
        }


def main():
    """
    Main entry point for desktop agent.

    PHASE3-AGENT-001: CLI entry point for PyInstaller.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Fogburst Desktop Agent")
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to config file"
    )
    parser.add_argument(
        "--coordinator", "-u",
        type=str,
        help="Coordinator URL (overrides config)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Load config
    config = AgentConfig.load(args.config)
    if args.coordinator:
        config.coordinator_url = args.coordinator

    # Create and run agent
    agent = DesktopAgent(config)

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Agent interrupted")


if __name__ == "__main__":
    main()
