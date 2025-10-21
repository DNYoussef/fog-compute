"""
WebSocket Metrics Streamer
Provides real-time metrics updates to connected clients
"""
from fastapi import WebSocket
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MetricsStreamer:
    """Streams real-time metrics to WebSocket clients"""

    def __init__(self, service_manager):
        self.service_manager = service_manager
        self.update_interval = 1.0  # seconds

    async def stream_metrics(self, websocket: WebSocket):
        """
        Stream metrics to a WebSocket client

        Args:
            websocket: Connected WebSocket client

        Streams updates every second with all service metrics
        """
        try:
            while True:
                # Gather metrics from all services
                metrics = await self.gather_metrics()

                # Send to client
                await websocket.send_json(metrics)

                # Wait for next update
                await asyncio.sleep(self.update_interval)

        except asyncio.CancelledError:
            logger.info("Metrics streaming cancelled")
        except Exception as e:
            logger.error(f"Error streaming metrics: {e}")
            raise

    async def gather_metrics(self) -> Dict[str, Any]:
        """
        Gather metrics from all services

        Returns:
            Dictionary with metrics from all services
        """
        try:
            # Get service instances
            betanet = self.service_manager.get('betanet')
            p2p = self.service_manager.get('p2p')
            scheduler = self.service_manager.get('scheduler')
            edge = self.service_manager.get('edge')
            dao = self.service_manager.get('dao')
            onion = self.service_manager.get('onion')

            # Betanet metrics
            betanet_status = await betanet.get_status() if betanet else {}

            # P2P metrics
            p2p_health = p2p.get_health() if p2p and hasattr(p2p, 'get_health') else {}

            # Scheduler metrics
            scheduler_jobs = scheduler.get_job_queue() if scheduler and hasattr(scheduler, 'get_job_queue') else []
            pending_jobs = [j for j in scheduler_jobs if getattr(j, 'status', None) == 'pending']
            running_jobs = [j for j in scheduler_jobs if getattr(j, 'status', None) == 'running']

            # Edge metrics
            devices = edge.get_registered_devices() if edge and hasattr(edge, 'get_registered_devices') else []
            harvesting = [d for d in devices if getattr(d, 'status', None) == 'harvesting']

            # Tokenomics metrics
            total_supply = dao.token_manager.total_supply if dao and hasattr(dao, 'token_manager') else 0
            stakes = dao.token_manager.stakes if dao and hasattr(dao, 'token_manager') else {}

            # Privacy metrics
            circuits = onion.get_active_circuits() if onion and hasattr(onion, 'get_active_circuits') else []

            return {
                "timestamp": datetime.now().isoformat(),
                "betanet": {
                    "active_nodes": betanet_status.get('active_nodes', 0),
                    "connections": betanet_status.get('connections', 0),
                    "latency_ms": betanet_status.get('avg_latency_ms', 0),
                    "packets": betanet_status.get('packets_processed', 0)
                },
                "p2p": {
                    "connected_peers": p2p_health.get('connected_peers', 0),
                    "messages_sent": p2p_health.get('messages_sent', 0),
                    "messages_received": p2p_health.get('messages_received', 0)
                },
                "scheduler": {
                    "pending": len(pending_jobs),
                    "running": len(running_jobs),
                    "total": len(scheduler_jobs)
                },
                "idle_compute": {
                    "total_devices": len(devices),
                    "harvesting": len(harvesting)
                },
                "tokenomics": {
                    "total_supply": total_supply,
                    "stakers": len(stakes)
                },
                "privacy": {
                    "circuits": len(circuits)
                }
            }

        except Exception as e:
            logger.error(f"Error gathering metrics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
