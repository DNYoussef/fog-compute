"""
Contract test fixtures.

Loads canonical JSON schemas from docs/contracts/ and provides fixtures for tests.
"""
import sys
import os
import pytest
from pathlib import Path

# Ensure the contracts directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema_helpers import load_schema


@pytest.fixture
def betanet_status_schema():
    return load_schema("betanet-status.schema.json")


@pytest.fixture
def betanet_node_schema():
    return load_schema("betanet-node.schema.json")


@pytest.fixture
def idle_device_schema():
    return load_schema("idle-device.schema.json")


@pytest.fixture
def benchmark_data_schema():
    return load_schema("benchmark-data.schema.json")
