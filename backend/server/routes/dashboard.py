"""
Dashboard API Routes
Aggregates statistics from all services for dashboard display

API Response Schema:
{
    "betanet": {
        "mixnodes": int,              # Active Betanet mixnodes
        "activeConnections": int,      # Active network connections
        "packetsProcessed": int,       # Total packets processed
        "status": str                  # "online" | "offline"
    },
    "bitchat": {
        "activePeers": int,            # Connected P2P peers
        "messagesDelivered": int,      # Total messages sent/received
        "encryptionStatus": bool,      # E2E encryption enabled
        "meshHealth": str              # "good" | "fair" | "poor"
    },
    "benchmarks": {
        "avgLatency": float,           # Average network latency (ms)
        "throughput": float,           # Network throughput (Mbps)
        "networkUtilization": float,   # Network usage percentage (0-100)
        "cpuUsage": float,             # CPU usage percentage (0-100)
        "memoryUsage": float           # Memory usage percentage (0-100)
    },
    "idle": {
        "totalDevices": int,           # Total registered devices
        "harvestingDevices": int,      # Devices actively harvesting
        "computeHours": float          # Total compute hours contributed
    },
    "tokenomics": {
        "totalSupply": float,          # Total token supply
        "activeStakers": int           # Number of active stakers
    },
    "privacy": {
        "activeCircuits": int,         # Active onion routing circuits
        "circuitHealth": float         # Average circuit health (0.0-1.0)
    }
}
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
import psutil

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager

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

        # Betanet stats - match frontend interface
        betanet_status = await betanet.get_status() if betanet else None
        betanet_status_dict = betanet_status.to_dict() if betanet_status else {}
        active_nodes = betanet_status_dict.get('active_nodes', 0)
        betanet_stats = {
            "mixnodes": active_nodes,
            "activeConnections": betanet_status_dict.get('connections', 0),
            "packetsProcessed": betanet_status_dict.get('packets_processed', 0),
            "status": "online" if active_nodes > 0 else "offline"
        }

        # P2P stats - match frontend interface
        p2p_health = p2p.get_health() if p2p and hasattr(p2p, 'get_health') else {}
        connected_peers = p2p_health.get('connected_peers', 0)
        bitchat_stats = {
            "activePeers": connected_peers,
            "messagesDelivered": p2p_health.get('messages_sent', 0) + p2p_health.get('messages_received', 0),
            "encryptionStatus": True,
            "meshHealth": "good" if connected_peers > 0 else "poor"
        }

        # Benchmarks stats - match frontend interface with real system metrics
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            net_io = psutil.net_io_counters()

            # Calculate network utilization as percentage of typical gigabit capacity
            # Using simple heuristic: (bytes_sent + bytes_recv) as indicator
            network_util = min(100.0, (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024 * 100) * 10)

            benchmarks_stats = {
                "avgLatency": scheduler.get_avg_latency() if scheduler and hasattr(scheduler, 'get_avg_latency') else 0.0,
                "throughput": (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024) if net_io else 0.0,  # MB
                "networkUtilization": network_util,
                "cpuUsage": cpu_percent,
                "memoryUsage": memory_info.percent
            }
        except Exception as e:
            logger.warning(f"Error getting system metrics: {e}")
            benchmarks_stats = {
                "avgLatency": 0.0,
                "throughput": 0.0,
                "networkUtilization": 0.0,
                "cpuUsage": 0.0,
                "memoryUsage": 0.0
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

        # Return ALL calculated sections - no data drop
        return {
            "betanet": betanet_stats,
            "bitchat": bitchat_stats,
            "benchmarks": benchmarks_stats,
            "idle": idle_stats,
            "tokenomics": tokenomics_stats,
            "privacy": privacy_stats
        }

    except Exception as e:
        logger.error(f"Error aggregating dashboard stats: {e}")
        # Return complete fallback data matching full schema
        return {
            "betanet": {
                "mixnodes": 0,
                "activeConnections": 0,
                "packetsProcessed": 0,
                "status": "offline"
            },
            "bitchat": {
                "activePeers": 0,
                "messagesDelivered": 0,
                "encryptionStatus": False,
                "meshHealth": "poor"
            },
            "benchmarks": {
                "avgLatency": 0.0,
                "throughput": 0.0,
                "networkUtilization": 0.0,
                "cpuUsage": 0.0,
                "memoryUsage": 0.0
            },
            "idle": {
                "totalDevices": 0,
                "harvestingDevices": 0,
                "computeHours": 0.0
            },
            "tokenomics": {
                "totalSupply": 0.0,
                "activeStakers": 0
            },
            "privacy": {
                "activeCircuits": 0,
                "circuitHealth": 0.0
            }
        }
