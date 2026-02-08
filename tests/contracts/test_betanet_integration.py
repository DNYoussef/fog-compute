"""
Integration tests for Betanet service and client (Phase 1).

Tests SIN-001 (Timeout), SIN-002 (deploy signature), SIN-003 (backend CRUD),
SIN-004 (schema adapter), SIN-005 (Prometheus parse).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from schema_helpers import load_schema, assert_matches_schema


class TestBetanetClientTimeout:
    """SIN-001: httpx.Timeout must have all 4 fields."""

    def test_timeout_has_all_fields(self):
        import httpx
        from backend.server.services.betanet_client import BetanetClient

        client = BetanetClient(url="http://localhost:9000", timeout=5, read_timeout=10)
        t = client.timeout
        assert isinstance(t, httpx.Timeout)
        assert t.connect == 5.0
        assert t.read == 10.0
        assert t.write == 5.0
        assert t.pool == 5.0


class TestPrometheusParser:
    """SIN-005: Parse Prometheus text format."""

    def test_parse_prometheus_text(self):
        from backend.server.services.betanet_client import _parse_prometheus_text

        text = """# HELP betanet_nodes_total Total mixnodes
# TYPE betanet_nodes_total gauge
betanet_nodes_total 5
# HELP betanet_avg_latency_ms Avg latency
# TYPE betanet_avg_latency_ms gauge
betanet_avg_latency_ms 42.5
"""
        result = _parse_prometheus_text(text)
        assert result["betanet_nodes_total"] == 5.0
        assert result["betanet_avg_latency_ms"] == 42.5

    def test_parse_empty_text(self):
        from backend.server.services.betanet_client import _parse_prometheus_text

        assert _parse_prometheus_text("") == {}
        assert _parse_prometheus_text("# only comments\n") == {}


class TestBetanetServiceCRUD:
    """SIN-003: Backend owns node CRUD."""

    @pytest.fixture
    def service(self):
        from backend.server.services.betanet import BetanetService
        return BetanetService(client=None)

    @pytest.mark.asyncio
    async def test_create_node(self, service):
        node = await service.create_node(node_type="mixnode", region="us-east", name="test")
        assert node["node_type"] == "mixnode"
        assert node["region"] == "us-east"
        assert node["name"] == "test"
        assert node["id"]  # has an id
        assert node["status"] in ("deploying", "active")

    @pytest.mark.asyncio
    async def test_list_nodes_empty(self, service):
        nodes = await service.list_nodes()
        assert nodes == []

    @pytest.mark.asyncio
    async def test_list_nodes_after_create(self, service):
        await service.create_node(node_type="mixnode")
        nodes = await service.list_nodes()
        assert len(nodes) == 1

    @pytest.mark.asyncio
    async def test_get_node(self, service):
        created = await service.create_node(node_type="gateway")
        fetched = await service.get_node(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_node(self, service):
        result = await service.get_node("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_node(self, service):
        created = await service.create_node(node_type="mixnode")
        updated = await service.update_node(created["id"], {"name": "updated-name"})
        assert updated is not None
        assert updated["name"] == "updated-name"

    @pytest.mark.asyncio
    async def test_update_nonexistent_node(self, service):
        result = await service.update_node("nonexistent", {"name": "x"})
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_node(self, service):
        created = await service.create_node(node_type="mixnode")
        deleted = await service.delete_node(created["id"])
        assert deleted is True
        assert await service.get_node(created["id"]) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_node(self, service):
        assert await service.delete_node("nonexistent") is False


class TestBetanetNodeSchemaConformance:
    """SIN-004: Nodes match betanet-node.schema.json."""

    @pytest.fixture
    def schema(self):
        return load_schema("betanet-node.schema.json")

    @pytest.mark.asyncio
    async def test_created_node_matches_schema(self, schema):
        from backend.server.services.betanet import BetanetService

        svc = BetanetService(client=None)
        node = await svc.create_node(node_type="mixnode", region="eu-west", name="test")
        assert_matches_schema(node, schema)

    @pytest.mark.asyncio
    async def test_updated_node_matches_schema(self, schema):
        from backend.server.services.betanet import BetanetService

        svc = BetanetService(client=None)
        created = await svc.create_node(node_type="gateway")
        updated = await svc.update_node(created["id"], {"status": "maintenance"})
        assert_matches_schema(updated, schema)


class TestBetanetDeploySignature:
    """SIN-002: Deploy call signature must match between route and client."""

    def test_client_deploy_accepts_kwargs(self):
        """Verify deploy_node accepts keyword args directly."""
        from backend.server.services.betanet_client import BetanetClient
        import inspect

        sig = inspect.signature(BetanetClient.deploy_node)
        params = list(sig.parameters.keys())
        assert "node_type" in params
        assert "region" in params

    @pytest.mark.asyncio
    async def test_service_deploy_returns_expected_shape(self):
        from backend.server.services.betanet import BetanetService

        svc = BetanetService(client=None)
        result = await svc.deploy_node(node_type="mixnode", region="us-east")
        assert result["success"] is True
        assert "node_id" in result
        assert "status" in result


class TestBetanetSyncFromRust:
    """SIN-004: Adapter maps Rust schema to canonical."""

    @pytest.mark.asyncio
    async def test_sync_creates_nodes_from_rust(self):
        from backend.server.services.betanet import BetanetService

        mock_client = AsyncMock()
        mock_client.get_mixnodes.return_value = [
            {
                "id": "rust-node-1",
                "status": "active",
                "packets_processed": 100,
                "packets_forwarded": 90,
                "packets_dropped": 10,
                "uptime_seconds": 3600,
                "avg_latency_ms": 42.0,
            }
        ]

        svc = BetanetService(client=mock_client)
        synced = await svc.sync_from_rust()
        assert synced == 1

        nodes = await svc.list_nodes()
        assert len(nodes) == 1
        assert nodes[0]["id"] == "rust-node-1"
        assert nodes[0]["packets_processed"] == 100

    @pytest.mark.asyncio
    async def test_sync_updates_existing_nodes(self):
        from backend.server.services.betanet import BetanetService

        mock_client = AsyncMock()
        svc = BetanetService(client=mock_client)

        # Create a node first
        node = await svc.create_node(node_type="mixnode")

        # Simulate Rust returning updated metrics for this node
        mock_client.get_mixnodes.return_value = [
            {
                "id": node["id"],
                "status": "active",
                "packets_processed": 500,
                "packets_forwarded": 480,
                "packets_dropped": 20,
                "avg_latency_ms": 35.0,
            }
        ]

        synced = await svc.sync_from_rust()
        assert synced == 1

        updated = await svc.get_node(node["id"])
        assert updated["packets_processed"] == 500
