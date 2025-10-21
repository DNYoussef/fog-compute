"""
Betanet HTTP Client
Communicates with Betanet Rust service via HTTP
"""
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BetanetClient:
    """Client for communicating with Betanet Rust HTTP server"""

    def __init__(self, url: str = "http://localhost:9000", timeout: int = 5):
        self.url = url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get_status(self) -> Dict[str, Any]:
        """Get Betanet network status"""
        try:
            response = await self.client.get(f"{self.url}/status")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            logger.warning(f"Betanet service not available at {self.url}")
            return self._mock_status()
        except Exception as e:
            logger.error(f"Error fetching Betanet status: {e}")
            return self._mock_status()

    async def get_mixnodes(self) -> list[Dict[str, Any]]:
        """Get list of active mixnodes"""
        try:
            response = await self.client.get(f"{self.url}/mixnodes")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching mixnodes: {e}")
            return []

    async def get_metrics(self) -> Dict[str, Any]:
        """Get Prometheus metrics from Betanet"""
        try:
            response = await self.client.get(f"{self.url}/metrics")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching Betanet metrics: {e}")
            return {}

    async def deploy_node(self, node_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a new Betanet node"""
        try:
            response = await self.client.post(
                f"{self.url}/deploy",
                json=node_config
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error deploying Betanet node: {e}")
            return {"success": False, "error": str(e)}

    def _mock_status(self) -> Dict[str, Any]:
        """Return mock data when Betanet service is unavailable"""
        return {
            "status": "mock",
            "active_nodes": 0,
            "connections": 0,
            "avg_latency_ms": 0,
            "packets_processed": 0,
            "note": "Betanet Rust service not running - using mock data"
        }

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
