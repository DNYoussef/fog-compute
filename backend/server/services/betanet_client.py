"""
Betanet HTTP Client
Communicates with Betanet Rust service via HTTP

Fixes: SIN-001 (Timeout construction), SIN-002 (deploy signature),
       SIN-005 (Prometheus text parsing)
"""
import re
import httpx
import logging
from typing import Dict, Any, List

from backend.server.constants import (
    BETANET_CONNECTION_TIMEOUT,
    BETANET_READ_TIMEOUT,
)
from backend.server.mock_guard import guard_mock

logger = logging.getLogger(__name__)


def _parse_prometheus_text(text: str) -> Dict[str, float]:
    """Parse Prometheus exposition format into a flat dict of metric->value.

    SIN-005: Rust betanet /metrics returns Prometheus text, not JSON.
    """
    result: Dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(\S+)\s+([\d.eE+\-]+)$", line)
        if match:
            try:
                result[match.group(1)] = float(match.group(2))
            except ValueError:
                pass
    return result


class BetanetClient:
    """Client for communicating with Betanet Rust HTTP server"""

    def __init__(
        self,
        url: str = "http://localhost:9000",
        timeout: int = BETANET_CONNECTION_TIMEOUT,
        read_timeout: int = BETANET_READ_TIMEOUT,
    ):
        self.url = url.rstrip('/')
        # SIN-001: Provide all 4 Timeout fields explicitly.
        self.timeout = httpx.Timeout(
            connect=float(timeout),
            read=float(read_timeout),
            write=float(timeout),
            pool=float(timeout),
        )
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def get_status(self) -> Dict[str, Any]:
        """Get Betanet network status from Rust server."""
        try:
            response = await self.client.get(f"{self.url}/status")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            logger.warning("Betanet service not available at %s", self.url)
            guard_mock("betanet_client.get_status: Rust server unreachable")
            return self._mock_status()
        except Exception as e:
            logger.error("Error fetching Betanet status: %s", e)
            guard_mock("betanet_client.get_status: unexpected error")
            return self._mock_status()

    async def get_mixnodes(self) -> List[Dict[str, Any]]:
        """Get list of active mixnodes from Rust server."""
        try:
            response = await self.client.get(f"{self.url}/mixnodes")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Error fetching mixnodes: %s", e)
            return []

    async def get_metrics(self) -> Dict[str, float]:
        """Get metrics from Betanet Rust /metrics endpoint.

        SIN-005: Parses Prometheus text format (not JSON).
        Returns dict of metric_name -> float value.
        """
        try:
            response = await self.client.get(f"{self.url}/metrics")
            response.raise_for_status()
            return _parse_prometheus_text(response.text)
        except Exception as e:
            logger.error("Error fetching Betanet metrics: %s", e)
            return {}

    async def deploy_node(
        self, *, node_type: str, region: str | None = None, name: str | None = None
    ) -> Dict[str, Any]:
        """Deploy a new Betanet node via Rust /deploy endpoint.

        SIN-002: Accepts explicit keyword args matching the route caller,
        and builds the JSON body for the Rust DeployRequest.
        """
        payload = {"node_type": node_type}
        if region is not None:
            payload["region"] = region
        if name is not None:
            payload["name"] = name

        try:
            response = await self.client.post(
                f"{self.url}/deploy",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Error deploying Betanet node: %s", e)
            return {"success": False, "error": str(e)}

    def _mock_status(self) -> Dict[str, Any]:
        """Return mock data when Betanet service is unavailable."""
        return {
            "status": "mock",
            "active_nodes": 0,
            "connections": 0,
            "avg_latency_ms": 0,
            "packets_processed": 0,
            "note": "Betanet Rust service not running - using mock data",
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
