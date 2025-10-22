"""
Real-time Data Publishers
Publish system data to WebSocket rooms at configured intervals
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .server import connection_manager
from ..services.enhanced_service_manager import enhanced_service_manager

logger = logging.getLogger(__name__)


class DataPublisher:
    """Base class for data publishers"""

    def __init__(self, room: str, interval: float):
        self.room = room
        self.interval = interval
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start publishing"""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._publish_loop())
        logger.info(f"Started publisher for room '{self.room}' (interval: {self.interval}s)")

    async def stop(self):
        """Stop publishing"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped publisher for room '{self.room}'")

    async def _publish_loop(self):
        """Main publishing loop"""
        while self.running:
            try:
                data = await self.collect_data()
                if data:
                    await connection_manager.broadcast_to_room(data, self.room)
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Publisher error in room '{self.room}': {e}")
                await asyncio.sleep(self.interval)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Collect data to publish - override in subclasses"""
        raise NotImplementedError


class NodeStatusPublisher(DataPublisher):
    """Publishes node status updates every 5 seconds"""

    def __init__(self):
        super().__init__("nodes", interval=5.0)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Collect node status from all services"""
        try:
            betanet = enhanced_service_manager.get('betanet')
            p2p = enhanced_service_manager.get('p2p')

            betanet_status = await betanet.get_status() if betanet else {}
            p2p_health = p2p.get_health() if p2p and hasattr(p2p, 'get_health') else {}

            return {
                "type": "node_status_update",
                "data": {
                    "betanet": {
                        "active_nodes": betanet_status.get('active_nodes', 0),
                        "connections": betanet_status.get('connections', 0),
                        "avg_latency_ms": betanet_status.get('avg_latency_ms', 0),
                        "packets_processed": betanet_status.get('packets_processed', 0)
                    },
                    "p2p": {
                        "connected_peers": p2p_health.get('connected_peers', 0),
                        "messages_sent": p2p_health.get('messages_sent', 0),
                        "messages_received": p2p_health.get('messages_received', 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error collecting node status: {e}")
            return None


class TaskProgressPublisher(DataPublisher):
    """Publishes task progress updates in real-time"""

    def __init__(self):
        super().__init__("tasks", interval=2.0)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Collect task progress from scheduler"""
        try:
            scheduler = enhanced_service_manager.get('scheduler')

            if not scheduler or not hasattr(scheduler, 'get_job_queue'):
                return None

            jobs = scheduler.get_job_queue()

            tasks = []
            for job in jobs:
                tasks.append({
                    "id": getattr(job, 'id', 'unknown'),
                    "name": getattr(job, 'name', 'unknown'),
                    "status": getattr(job, 'status', 'unknown'),
                    "progress": getattr(job, 'progress', 0),
                    "start_time": getattr(job, 'start_time', None),
                    "estimated_completion": getattr(job, 'estimated_completion', None)
                })

            return {
                "type": "task_progress_update",
                "data": {
                    "tasks": tasks,
                    "summary": {
                        "total": len(jobs),
                        "pending": len([j for j in jobs if getattr(j, 'status', None) == 'pending']),
                        "running": len([j for j in jobs if getattr(j, 'status', None) == 'running']),
                        "completed": len([j for j in jobs if getattr(j, 'status', None) == 'completed']),
                        "failed": len([j for j in jobs if getattr(j, 'status', None) == 'failed'])
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error collecting task progress: {e}")
            return None


class MetricsPublisher(DataPublisher):
    """Publishes performance metrics every 10 seconds"""

    def __init__(self):
        super().__init__("metrics", interval=10.0)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Collect performance metrics"""
        try:
            health = enhanced_service_manager.get_health()
            composite_health = enhanced_service_manager.health_manager.get_composite_health()

            return {
                "type": "metrics_update",
                "data": {
                    "composite_health": composite_health.value,
                    "services": health,
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return None


class AlertPublisher(DataPublisher):
    """Publishes alerts immediately"""

    def __init__(self):
        super().__init__("alerts", interval=1.0)
        self.alert_queue: asyncio.Queue = asyncio.Queue()

    async def publish_alert(self, alert: Dict[str, Any]):
        """Queue an alert for immediate publication"""
        await self.alert_queue.put(alert)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Check for queued alerts"""
        try:
            alert = await asyncio.wait_for(self.alert_queue.get(), timeout=0.1)
            return {
                "type": "alert",
                "data": alert,
                "priority": alert.get("severity", "info")
            }
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error collecting alerts: {e}")
            return None


class ResourcePublisher(DataPublisher):
    """Publishes resource utilization every 15 seconds"""

    def __init__(self):
        super().__init__("resources", interval=15.0)

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Collect resource utilization"""
        try:
            edge = enhanced_service_manager.get('edge')

            if not edge or not hasattr(edge, 'get_registered_devices'):
                return None

            devices = edge.get_registered_devices()

            total_cpu = sum(getattr(d, 'cpu_usage', 0) for d in devices)
            total_memory = sum(getattr(d, 'memory_usage', 0) for d in devices)
            total_storage = sum(getattr(d, 'storage_used', 0) for d in devices)

            return {
                "type": "resource_update",
                "data": {
                    "devices": len(devices),
                    "avg_cpu_usage": total_cpu / len(devices) if devices else 0,
                    "avg_memory_usage": total_memory / len(devices) if devices else 0,
                    "total_storage_used": total_storage,
                    "devices_details": [
                        {
                            "id": getattr(d, 'id', 'unknown'),
                            "cpu": getattr(d, 'cpu_usage', 0),
                            "memory": getattr(d, 'memory_usage', 0),
                            "storage": getattr(d, 'storage_used', 0),
                            "status": getattr(d, 'status', 'unknown')
                        }
                        for d in devices[:10]  # Limit to first 10 for bandwidth
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Error collecting resources: {e}")
            return None


class TopologyPublisher(DataPublisher):
    """Publishes network topology changes on change detection"""

    def __init__(self):
        super().__init__("topology", interval=5.0)
        self.last_topology_hash = None

    async def collect_data(self) -> Optional[Dict[str, Any]]:
        """Collect network topology"""
        try:
            betanet = enhanced_service_manager.get('betanet')

            if not betanet:
                return None

            status = await betanet.get_status()

            # Create a simple hash of topology state
            topology_state = f"{status.get('active_nodes', 0)}_{status.get('connections', 0)}"

            # Only publish if topology changed
            if topology_state == self.last_topology_hash:
                return None

            self.last_topology_hash = topology_state

            return {
                "type": "topology_change",
                "data": {
                    "active_nodes": status.get('active_nodes', 0),
                    "connections": status.get('connections', 0),
                    "network_map": status.get('network_map', {})
                }
            }
        except Exception as e:
            logger.error(f"Error collecting topology: {e}")
            return None


class PublisherManager:
    """Manages all data publishers"""

    def __init__(self):
        self.publishers = []
        self.alert_publisher: Optional[AlertPublisher] = None

    async def start_all(self):
        """Start all publishers"""
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

        for publisher in self.publishers:
            await publisher.start()

        logger.info(f"Started {len(self.publishers)} data publishers")

    async def stop_all(self):
        """Stop all publishers"""
        for publisher in self.publishers:
            await publisher.stop()

        self.publishers = []
        self.alert_publisher = None
        logger.info("Stopped all data publishers")

    async def publish_alert(self, alert: Dict[str, Any]):
        """Publish an alert immediately"""
        if self.alert_publisher:
            await self.alert_publisher.publish_alert(alert)


# Global publisher manager instance
publisher_manager = PublisherManager()
