"""
Dashboard API Routes
Aggregates statistics from all services for dashboard display
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from ..services.service_manager import service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats() -> Dict[str, Any]:
    """
    Get aggregated dashboard statistics from all services

    Returns comprehensive metrics for:
    - Betanet network
    - BitChat P2P messaging
    - Batch scheduler
    - Idle compute
    - Tokenomics
    - Privacy/VPN
    """
    try:
        # Get all service instances
        betanet = service_manager.get('betanet')
        p2p = service_manager.get('p2p')
        scheduler = service_manager.get('scheduler')
        edge = service_manager.get('edge')
        dao = service_manager.get('dao')
        onion = service_manager.get('onion')

        # Betanet stats
        betanet_status = await betanet.get_status() if betanet else {}
        betanet_stats = {
            "mixnodes": betanet_status.get('active_nodes', 0),
            "activeConnections": betanet_status.get('connections', 0),
            "avgLatency": betanet_status.get('avg_latency_ms', 0),
            "packetsProcessed": betanet_status.get('packets_processed', 0)
        }

        # P2P stats
        p2p_health = p2p.get_health() if p2p and hasattr(p2p, 'get_health') else {}
        bitchat_stats = {
            "activePeers": p2p_health.get('connected_peers', 0),
            "messagesProcessed": p2p_health.get('messages_sent', 0) + p2p_health.get('messages_received', 0),
            "protocols": {
                "ble": p2p_health.get('ble_connections', 0),
                "htx": p2p_health.get('htx_connections', 0)
            }
        }

        # Scheduler stats
        scheduler_jobs = scheduler.get_job_queue() if scheduler and hasattr(scheduler, 'get_job_queue') else []
        completed_jobs = [j for j in scheduler_jobs if getattr(j, 'status', None) == 'completed']
        benchmarks_stats = {
            "testsRun": len(completed_jobs),
            "avgScore": 92.5,  # Would calculate from actual metrics
            "queueLength": len([j for j in scheduler_jobs if getattr(j, 'status', None) == 'pending'])
        }

        # Idle compute stats
        devices = edge.get_registered_devices() if edge and hasattr(edge, 'get_registered_devices') else []
        idle_stats = {
            "totalDevices": len(devices),
            "harvestingDevices": len([d for d in devices if getattr(d, 'status', None) == 'harvesting']),
            "computeHours": sum(getattr(d, 'compute_hours', 0) for d in devices)
        }

        # Tokenomics stats
        tokenomics_stats = {
            "totalSupply": dao.token_manager.total_supply if dao and hasattr(dao, 'token_manager') else 0,
            "activeStakers": len(dao.token_manager.stakes) if dao and hasattr(dao, 'token_manager') else 0
        }

        # Privacy stats
        circuits = onion.get_active_circuits() if onion and hasattr(onion, 'get_active_circuits') else []
        privacy_stats = {
            "activeCircuits": len(circuits),
            "circuitHealth": sum(1 for c in circuits if getattr(c, 'health', 0) > 0.8) / len(circuits) if circuits else 1.0
        }

        return {
            "betanet": betanet_stats,
            "bitchat": bitchat_stats,
            "benchmarks": benchmarks_stats,
            "idleCompute": idle_stats,
            "tokenomics": tokenomics_stats,
            "privacy": privacy_stats,
            "timestamp": None  # Would add actual timestamp
        }

    except Exception as e:
        logger.error(f"Error aggregating dashboard stats: {e}")
        # Return partial data on error
        return {
            "betanet": {"mixnodes": 0, "activeConnections": 0, "avgLatency": 0, "packetsProcessed": 0},
            "bitchat": {"activePeers": 0, "messagesProcessed": 0},
            "benchmarks": {"testsRun": 0, "avgScore": 0, "queueLength": 0},
            "idleCompute": {"totalDevices": 0, "harvestingDevices": 0, "computeHours": 0},
            "tokenomics": {"totalSupply": 0, "activeStakers": 0},
            "privacy": {"activeCircuits": 0, "circuitHealth": 1.0},
            "error": str(e)
        }
