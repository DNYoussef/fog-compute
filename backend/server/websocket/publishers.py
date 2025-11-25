"""
Real-time Data Publishers
Publish system data to WebSocket rooms at configured intervals
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

from .server import connection_manager
from ..services.enhanced_service_manager import enhanced_service_manager

logger = logging.getLogger(__name__)


class DataPublisher(ABC):
    """
    Abstract base class for data publishers

    Provides lifecycle management and automatic publishing loop.
    Subclasses must implement collect_data() to provide data.

    Features:
    - Automatic retry on errors
    - Graceful shutdown
    - Error logging
    - Statistics tracking
    """

    def __init__(self, room: str, interval: float):
        """
        Initialize publisher

        Args:
            room: WebSocket room name to publish to
            interval: Publishing interval in seconds
        """
        self.room = room
        self.interval = interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._publish_count = 0
        self._error_count = 0
        self._last_publish_time: Optional[datetime] = None

    async def start(self):
        """Start publishing data"""
        if self.running:
            logger.warning(f"Publisher for room '{self.room}' already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._publish_loop())
        logger.info(f"Started publisher for room '{self.room}' (interval: {self.interval}s)")

    async def stop(self):
        """Stop publishing and cleanup"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug(f"Publisher task for room '{self.room}' cancelled successfully")
        logger.info(f"Stopped publisher for room '{self.room}' (published: {self._publish_count}, errors: {self._error_count})")

    async def _publish_loop(self):
        """
        Main publishing loop

        Continuously collects and publishes data at configured intervals.
        Handles errors gracefully without stopping the loop.
        """
        consecutive_errors = 0
        max_consecutive_errors = 10

        while self.running:
            try:
                data = await self.collect_data()
                if data:
                    await connection_manager.broadcast_to_room(data, self.room)
                    self._publish_count += 1
                    self._last_publish_time = datetime.now()
                    consecutive_errors = 0  # Reset on success
                    logger.debug(f"Published data to room '{self.room}' (count: {self._publish_count})")
                else:
                    logger.debug(f"No data collected for room '{self.room}' (may be normal)")

                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                logger.info(f"Publisher for room '{self.room}' cancelled")
                break
            except Exception as e:
                self._error_count += 1
                consecutive_errors += 1
                logger.error(
                    f"Publisher error in room '{self.room}' (consecutive: {consecutive_errors}/{max_consecutive_errors}): {e}",
                    exc_info=True
                )

                # If too many consecutive errors, increase backoff
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Publisher for room '{self.room}' has {consecutive_errors} consecutive errors, increasing backoff")
                    await asyncio.sleep(self.interval * 5)  # 5x backoff
                else:
                    await asyncio.sleep(self.interval)

    @abstractmethod
    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect data to publish

        Subclasses must implement this method to provide data for publishing.

        Returns:
            Dictionary with data to publish, or None if no data available
            Expected format: {"type": "message_type", "data": {...}}
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Get publisher statistics

        Returns:
            Dictionary with stats like publish count, error count, etc.
        """
        return {
            "room": self.room,
            "interval": self.interval,
            "running": self.running,
            "publish_count": self._publish_count,
            "error_count": self._error_count,
            "last_publish_time": self._last_publish_time.isoformat() if self._last_publish_time else None
        }


class NodeStatusPublisher(DataPublisher):
    """
    Publishes node status updates every 5 seconds

    Collects data from:
    - Betanet service: active nodes, connections, latency, packet throughput
    - P2P service: connected peers, message counts
    """

    def __init__(self):
        super().__init__("nodes", interval=5.0)
        self._service_warnings_shown = set()

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect node status from all network services

        Returns:
            Node status data or None if all services unavailable
        """
        try:
            betanet = enhanced_service_manager.get('betanet')
            p2p = enhanced_service_manager.get('p2p')

            # Warn once if services are missing
            if not betanet and 'betanet' not in self._service_warnings_shown:
                logger.warning("Betanet service not available for node status publishing")
                self._service_warnings_shown.add('betanet')
            if not p2p and 'p2p' not in self._service_warnings_shown:
                logger.warning("P2P service not available for node status publishing")
                self._service_warnings_shown.add('p2p')

            # Collect betanet status
            betanet_status = {}
            if betanet:
                try:
                    betanet_status = await betanet.get_status()
                except Exception as e:
                    logger.debug(f"Could not get betanet status: {e}")

            # Collect P2P health
            p2p_health = {}
            if p2p and hasattr(p2p, 'get_health'):
                try:
                    p2p_health = p2p.get_health()
                except Exception as e:
                    logger.debug(f"Could not get P2P health: {e}")

            # Return data even if some services are unavailable
            return {
                "type": "node_status_update",
                "data": {
                    "betanet": {
                        "active_nodes": betanet_status.get('active_nodes', 0),
                        "connections": betanet_status.get('connections', 0),
                        "avg_latency_ms": betanet_status.get('avg_latency_ms', 0),
                        "packets_processed": betanet_status.get('packets_processed', 0),
                        "available": bool(betanet and betanet_status)
                    },
                    "p2p": {
                        "connected_peers": p2p_health.get('connected_peers', 0),
                        "messages_sent": p2p_health.get('messages_sent', 0),
                        "messages_received": p2p_health.get('messages_received', 0),
                        "available": bool(p2p and p2p_health)
                    },
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting node status: {e}", exc_info=True)
            return None


class TaskProgressPublisher(DataPublisher):
    """
    Publishes task progress updates in real-time (every 2 seconds)

    Monitors the scheduler service for job queue status and progress.
    Provides per-task details and aggregate summary.
    """

    def __init__(self):
        super().__init__("tasks", interval=2.0)
        self._scheduler_warning_shown = False

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect task progress from scheduler service

        Returns:
            Task progress data with individual tasks and summary, or None if scheduler unavailable
        """
        try:
            scheduler = enhanced_service_manager.get('scheduler')

            if not scheduler:
                if not self._scheduler_warning_shown:
                    logger.warning("Scheduler service not available for task progress publishing")
                    self._scheduler_warning_shown = True
                return None

            if not hasattr(scheduler, 'get_job_queue'):
                if not self._scheduler_warning_shown:
                    logger.warning("Scheduler service does not support get_job_queue()")
                    self._scheduler_warning_shown = True
                return None

            # Collect job queue
            try:
                jobs = scheduler.get_job_queue()
            except Exception as e:
                logger.error(f"Error calling scheduler.get_job_queue(): {e}")
                return None

            # Transform jobs to task data
            tasks = []
            for job in jobs:
                try:
                    task_data = {
                        "id": getattr(job, 'id', 'unknown'),
                        "name": getattr(job, 'name', 'unknown'),
                        "status": getattr(job, 'status', 'unknown'),
                        "progress": getattr(job, 'progress', 0),
                        "start_time": getattr(job, 'start_time', None),
                        "estimated_completion": getattr(job, 'estimated_completion', None)
                    }
                    tasks.append(task_data)
                except Exception as e:
                    logger.debug(f"Error extracting task data from job: {e}")

            # Calculate summary statistics
            summary = {
                "total": len(jobs),
                "pending": len([j for j in jobs if getattr(j, 'status', None) == 'pending']),
                "running": len([j for j in jobs if getattr(j, 'status', None) == 'running']),
                "completed": len([j for j in jobs if getattr(j, 'status', None) == 'completed']),
                "failed": len([j for j in jobs if getattr(j, 'status', None) == 'failed'])
            }

            return {
                "type": "task_progress_update",
                "data": {
                    "tasks": tasks,
                    "summary": summary,
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting task progress: {e}", exc_info=True)
            return None


class MetricsPublisher(DataPublisher):
    """
    Publishes performance metrics every 10 seconds

    Collects:
    - Composite health score for the entire system
    - Individual service health status
    - Timestamps for tracking
    """

    def __init__(self):
        super().__init__("metrics", interval=10.0)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect performance metrics from service manager

        Returns:
            Metrics data with composite health and per-service health, or None on error
        """
        try:
            # Get service health data
            health = enhanced_service_manager.get_health()

            # Get composite health score
            composite_health_value = "unknown"
            try:
                if hasattr(enhanced_service_manager, 'health_manager'):
                    composite_health = enhanced_service_manager.health_manager.get_composite_health()
                    composite_health_value = composite_health.value if hasattr(composite_health, 'value') else str(composite_health)
            except Exception as e:
                logger.debug(f"Could not get composite health: {e}")

            return {
                "type": "metrics_update",
                "data": {
                    "composite_health": composite_health_value,
                    "services": health,
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
            return None


class AlertPublisher(DataPublisher):
    """
    Publishes alerts immediately via queue mechanism

    Alerts can be queued by other parts of the system and will be
    published to WebSocket clients as soon as possible (1 second poll interval).

    Features:
    - Priority-based alert handling
    - Queue-based alert delivery
    - Immediate publication of critical alerts
    """

    def __init__(self):
        super().__init__("alerts", interval=1.0)
        self.alert_queue: asyncio.Queue = asyncio.Queue()
        self._alert_count = 0

    async def publish_alert(self, alert: Dict[str, Any]):
        """
        Queue an alert for immediate publication

        Args:
            alert: Alert dictionary with at minimum {"severity": "...", "message": "..."}
        """
        self._alert_count += 1
        await self.alert_queue.put(alert)
        logger.info(f"Alert queued (#{self._alert_count}): severity={alert.get('severity', 'unknown')}, message={alert.get('message', 'N/A')[:50]}")

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Check for queued alerts

        Returns:
            Alert data if available, None if queue empty
        """
        try:
            # Wait briefly for an alert (non-blocking with timeout)
            alert = await asyncio.wait_for(self.alert_queue.get(), timeout=0.1)

            return {
                "type": "alert",
                "data": alert,
                "priority": alert.get("severity", "info"),
                "timestamp": datetime.now().isoformat()
            }
        except asyncio.TimeoutError:
            # No alerts in queue - this is normal
            return None
        except Exception as e:
            logger.error(f"Error collecting alerts: {e}", exc_info=True)
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get alert publisher statistics"""
        stats = super().get_stats()
        stats['total_alerts'] = self._alert_count
        stats['queued_alerts'] = self.alert_queue.qsize()
        return stats


class ResourcePublisher(DataPublisher):
    """
    Publishes resource utilization every 15 seconds

    Monitors edge devices for:
    - CPU usage
    - Memory usage
    - Storage utilization
    - Device status

    Provides aggregate statistics and top 10 device details.
    """

    def __init__(self):
        super().__init__("resources", interval=15.0)
        self._edge_warning_shown = False

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect resource utilization from edge devices

        Returns:
            Resource data with aggregates and device details, or None if edge service unavailable
        """
        try:
            edge = enhanced_service_manager.get('edge')

            if not edge:
                if not self._edge_warning_shown:
                    logger.warning("Edge service not available for resource publishing")
                    self._edge_warning_shown = True
                return None

            if not hasattr(edge, 'get_registered_devices'):
                if not self._edge_warning_shown:
                    logger.warning("Edge service does not support get_registered_devices()")
                    self._edge_warning_shown = True
                return None

            # Get registered devices
            try:
                devices = edge.get_registered_devices()
            except Exception as e:
                logger.error(f"Error calling edge.get_registered_devices(): {e}")
                return None

            # Calculate aggregate statistics
            total_cpu = sum(getattr(d, 'cpu_usage', 0) for d in devices)
            total_memory = sum(getattr(d, 'memory_usage', 0) for d in devices)
            total_storage = sum(getattr(d, 'storage_used', 0) for d in devices)
            device_count = len(devices)

            # Extract top 10 devices for detailed view
            devices_details = []
            for d in devices[:10]:  # Limit to first 10 for bandwidth
                try:
                    devices_details.append({
                        "id": getattr(d, 'id', 'unknown'),
                        "cpu": getattr(d, 'cpu_usage', 0),
                        "memory": getattr(d, 'memory_usage', 0),
                        "storage": getattr(d, 'storage_used', 0),
                        "status": getattr(d, 'status', 'unknown')
                    })
                except Exception as e:
                    logger.debug(f"Error extracting device details: {e}")

            return {
                "type": "resource_update",
                "data": {
                    "devices": device_count,
                    "avg_cpu_usage": total_cpu / device_count if device_count > 0 else 0,
                    "avg_memory_usage": total_memory / device_count if device_count > 0 else 0,
                    "total_storage_used": total_storage,
                    "devices_details": devices_details,
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting resources: {e}", exc_info=True)
            return None


class TopologyPublisher(DataPublisher):
    """
    Publishes network topology changes on change detection

    Only publishes when the topology actually changes to reduce
    unnecessary WebSocket traffic. Monitors betanet for:
    - Active node count
    - Connection count
    - Network topology map

    Features change detection via simple state hashing.
    """

    def __init__(self):
        super().__init__("topology", interval=5.0)
        self.last_topology_hash = None
        self._betanet_warning_shown = False
        self._change_count = 0

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect network topology (only on changes)

        Returns:
            Topology data if changed, None if unchanged or betanet unavailable
        """
        try:
            betanet = enhanced_service_manager.get('betanet')

            if not betanet:
                if not self._betanet_warning_shown:
                    logger.warning("Betanet service not available for topology publishing")
                    self._betanet_warning_shown = True
                return None

            # Get betanet status
            try:
                status = await betanet.get_status()
            except Exception as e:
                logger.error(f"Error calling betanet.get_status(): {e}")
                return None

            # Create a simple hash of topology state
            active_nodes = status.get('active_nodes', 0)
            connections = status.get('connections', 0)
            topology_state = f"{active_nodes}_{connections}"

            # Only publish if topology changed
            if topology_state == self.last_topology_hash:
                logger.debug(f"Topology unchanged (nodes={active_nodes}, connections={connections})")
                return None

            # Topology changed - update hash and publish
            self.last_topology_hash = topology_state
            self._change_count += 1

            logger.info(f"Topology changed (#{self._change_count}): nodes={active_nodes}, connections={connections}")

            return {
                "type": "topology_change",
                "data": {
                    "active_nodes": active_nodes,
                    "connections": connections,
                    "network_map": status.get('network_map', {}),
                    "change_number": self._change_count,
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting topology: {e}", exc_info=True)
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get topology publisher statistics"""
        stats = super().get_stats()
        stats['topology_changes'] = self._change_count
        return stats


class PublisherManager:
    """
    Manages all data publishers

    Coordinates lifecycle of all publisher instances:
    - NodeStatusPublisher (nodes room, 5s interval)
    - TaskProgressPublisher (tasks room, 2s interval)
    - MetricsPublisher (metrics room, 10s interval)
    - ResourcePublisher (resources room, 15s interval)
    - TopologyPublisher (topology room, 5s interval)
    - AlertPublisher (alerts room, 1s interval)

    Features:
    - Graceful startup/shutdown
    - Statistics aggregation
    - Manual alert publishing
    """

    def __init__(self):
        self.publishers = []
        self.alert_publisher: Optional[AlertPublisher] = None
        self._started = False

    async def start_all(self):
        """
        Start all publishers

        Creates and starts all publisher instances. Publishers will
        begin collecting and broadcasting data to their respective rooms.
        """
        if self._started:
            logger.warning("Publishers already started")
            return

        logger.info("Starting all data publishers...")

        try:
            # Create all publisher instances
            self.publishers = [
                NodeStatusPublisher(),
                TaskProgressPublisher(),
                MetricsPublisher(),
                ResourcePublisher(),
                TopologyPublisher()
            ]

            # Keep reference to alert publisher for manual alerts
            self.alert_publisher = AlertPublisher()
            self.publishers.append(self.alert_publisher)

            # Start each publisher
            for publisher in self.publishers:
                try:
                    await publisher.start()
                    logger.debug(f"Started {publisher.__class__.__name__} for room '{publisher.room}'")
                except Exception as e:
                    logger.error(f"Failed to start {publisher.__class__.__name__}: {e}")

            self._started = True
            logger.info(f"Successfully started {len(self.publishers)} data publishers")

        except Exception as e:
            logger.error(f"Error starting publishers: {e}", exc_info=True)
            # Cleanup on failure
            await self.stop_all()

    async def stop_all(self):
        """
        Stop all publishers

        Gracefully stops all publisher instances and cleans up resources.
        """
        if not self._started and not self.publishers:
            logger.debug("Publishers not running")
            return

        logger.info("Stopping all data publishers...")

        # Stop each publisher
        for publisher in self.publishers:
            try:
                await publisher.stop()
                logger.debug(f"Stopped {publisher.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error stopping {publisher.__class__.__name__}: {e}")

        self.publishers = []
        self.alert_publisher = None
        self._started = False
        logger.info("All data publishers stopped")

    async def publish_alert(self, alert: Dict[str, Any]):
        """
        Publish an alert immediately

        Args:
            alert: Alert dictionary with at minimum {"severity": "...", "message": "..."}

        Raises:
            RuntimeError: If alert publisher not available
        """
        if not self.alert_publisher:
            logger.error("Alert publisher not available - publishers may not be started")
            raise RuntimeError("Alert publisher not available")

        await self.alert_publisher.publish_alert(alert)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics from all publishers

        Returns:
            Dictionary with per-publisher stats
        """
        return {
            "started": self._started,
            "publisher_count": len(self.publishers),
            "publishers": [
                {
                    "class": p.__class__.__name__,
                    "stats": p.get_stats()
                }
                for p in self.publishers
            ]
        }

    def is_running(self) -> bool:
        """Check if publishers are running"""
        return self._started and len(self.publishers) > 0


# Global publisher manager instance
publisher_manager = PublisherManager()
