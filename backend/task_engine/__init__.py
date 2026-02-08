"""
Fogburst Task Execution Engine
FOGBURST-004: Simple task runner that accepts jobs from coordinator,
executes them locally, and reports results back.

Supports compute tasks initially.
"""
from .runner import TaskRunner, TaskResult, TaskStatus
from .handlers import (
    TaskHandler,
    ComputeHandler,
    BenchmarkHandler,
    HealthCheckHandler,
)
from .engine import TaskEngine, EngineConfig

__all__ = [
    # Core
    "TaskRunner",
    "TaskResult",
    "TaskStatus",
    "TaskEngine",
    "EngineConfig",
    # Handlers
    "TaskHandler",
    "ComputeHandler",
    "BenchmarkHandler",
    "HealthCheckHandler",
]

__version__ = "0.1.0"
