"""
Contract tests for Betanet API endpoints (SIN-031).

These tests validate that backend responses conform to the canonical
JSON schemas defined in docs/contracts/.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from schema_helpers import assert_matches_schema


class TestBetanetStatusContract:
    """GET /api/betanet/status must match betanet-status.schema.json."""

    def test_valid_healthy_status(self, betanet_status_schema):
        payload = {
            "status": "healthy",
            "nodes": {"total": 5, "active": 3, "inactive": 2},
            "network": {
                "latency": 45.0,
                "bandwidth": 1024,
                "throughput": 850,
                "packetsProcessed": 22274,
            },
            "lastUpdated": "2026-02-08T00:00:00Z",
        }
        assert_matches_schema(payload, betanet_status_schema)

    def test_valid_unavailable_status(self, betanet_status_schema):
        payload = {
            "status": "unavailable",
            "nodes": {"total": 0, "active": 0, "inactive": 0},
            "network": {
                "latency": 0,
                "bandwidth": 0,
                "throughput": 0,
                "packetsProcessed": 0,
            },
            "lastUpdated": None,
        }
        assert_matches_schema(payload, betanet_status_schema)

    def test_rejects_extra_fields(self, betanet_status_schema):
        payload = {
            "status": "healthy",
            "nodes": {"total": 1, "active": 1, "inactive": 0},
            "network": {
                "latency": 10,
                "bandwidth": 100,
                "throughput": 80,
                "packetsProcessed": 5000,
            },
            "lastUpdated": None,
            "extraField": "should fail",
        }
        with pytest.raises(AssertionError, match="Contract violation"):
            assert_matches_schema(payload, betanet_status_schema)

    def test_rejects_invalid_status_value(self, betanet_status_schema):
        payload = {
            "status": "unknown",
            "nodes": {"total": 0, "active": 0, "inactive": 0},
            "network": {
                "latency": 0,
                "bandwidth": 0,
                "throughput": 0,
                "packetsProcessed": 0,
            },
            "lastUpdated": None,
        }
        with pytest.raises(AssertionError, match="Contract violation"):
            assert_matches_schema(payload, betanet_status_schema)


class TestBetanetNodeContract:
    """Node objects must match betanet-node.schema.json."""

    def test_valid_node(self, betanet_node_schema):
        payload = {
            "id": "node-abc-123",
            "node_type": "mixnode",
            "region": "us-east",
            "name": "test-node",
            "status": "active",
            "packets_processed": 12453,
            "packets_forwarded": 11000,
            "packets_dropped": 53,
            "avg_latency_ms": 42.5,
            "created_at": "2026-02-08T00:00:00Z",
            "last_heartbeat": "2026-02-08T01:00:00Z",
        }
        assert_matches_schema(payload, betanet_node_schema)

    def test_rejects_invalid_node_type(self, betanet_node_schema):
        payload = {
            "id": "node-1",
            "node_type": "validator",
            "status": "active",
            "packets_processed": 0,
            "packets_forwarded": 0,
            "packets_dropped": 0,
            "avg_latency_ms": 0,
            "created_at": "2026-02-08T00:00:00Z",
            "last_heartbeat": "2026-02-08T00:00:00Z",
        }
        with pytest.raises(AssertionError, match="Contract violation"):
            assert_matches_schema(payload, betanet_node_schema)


class TestIdleDeviceContract:
    """Device objects must match idle-device.schema.json."""

    def test_valid_device(self, idle_device_schema):
        payload = {
            "id": "device-001",
            "type": "android",
            "status": "active",
            "capabilities": {
                "cpu": 8,
                "memory": 4096,
                "battery": 85.5,
                "charging": True,
                "temperature": 38.2,
            },
            "stats": {
                "tasksCompleted": 42,
                "computeHours": 12.5,
                "uptime": 3600,
            },
            "lastSeen": "2026-02-08T00:00:00Z",
        }
        assert_matches_schema(payload, idle_device_schema)


class TestBenchmarkDataContract:
    """GET /api/benchmarks/data must match benchmark-data.schema.json."""

    def test_valid_data(self, benchmark_data_schema):
        payload = {
            "timestamp": 1707350400000,
            "latency": 12.5,
            "throughput": 850.0,
            "cpuUsage": 45.2,
            "memoryUsage": 62.1,
            "networkUtilization": 38.7,
        }
        assert_matches_schema(payload, benchmark_data_schema)

    def test_rejects_negative_latency(self, benchmark_data_schema):
        payload = {
            "timestamp": 1707350400000,
            "latency": -5.0,
            "throughput": 0,
            "cpuUsage": 0,
            "memoryUsage": 0,
            "networkUtilization": 0,
        }
        with pytest.raises(AssertionError, match="Contract violation"):
            assert_matches_schema(payload, benchmark_data_schema)
