"""Universal component wiring for fog-compute backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from library.components.cognitive_architecture.integration.connascence_bridge import ConnascenceBridge
from library.components.cognitive_architecture.integration.telemetry_bridge import TelemetryBridge
from library.components.memory.memory_mcp_client import create_memory_mcp_client
from library.components.observability.tagging_protocol import TaggingProtocol, create_simple_tagger


def init_tagger() -> TaggingProtocol:
    return create_simple_tagger(agent_id="fog-compute", project_id="fog-compute")


def init_memory_client():
    endpoint = os.getenv("MEMORY_MCP_URL", "http://localhost:3000")
    return create_memory_mcp_client(
        project_id="fog-compute",
        project_name="fog-compute",
        agent_id="fog-compute",
        agent_category="backend",
        capabilities=["compute", "orchestration", "distributed"],
        mcp_endpoint=endpoint,
    )


def init_telemetry_bridge(loop_dir: Optional[str] = None) -> TelemetryBridge:
    resolved = Path(loop_dir) if loop_dir else Path(".loop")
    return TelemetryBridge(loop_dir=resolved)


def init_connascence_bridge() -> ConnascenceBridge:
    return ConnascenceBridge()

