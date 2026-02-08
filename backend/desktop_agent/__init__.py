"""
Fogburst Desktop Agent
Cross-platform desktop agent for fog computing mesh

PHASE3-AGENT-001: Cross-Platform Compatibility
PHASE3-AGENT-002: Sandboxed Task Execution
PHASE3-AGENT-003: Auto-Discovery + Manual Fallback
PHASE3-AGENT-004: Resource Limits Enforcement
"""
from .agent import DesktopAgent, AgentConfig, AgentStatus
from .executor import TaskExecutor, ExecutionResult
from .discovery import CoordinatorDiscovery, DiscoveryMethod
from .resource_monitor import ResourceMonitor, ResourceStatus, ResourceThresholds

__all__ = [
    "DesktopAgent",
    "AgentConfig",
    "AgentStatus",
    "TaskExecutor",
    "ExecutionResult",
    "CoordinatorDiscovery",
    "DiscoveryMethod",
    "ResourceMonitor",
    "ResourceStatus",
    "ResourceThresholds",
]

__version__ = "0.1.0"
