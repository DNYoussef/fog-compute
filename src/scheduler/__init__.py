"""
FOG Compute - Intelligent Scheduler Module

This module provides advanced resource optimization capabilities:
- Resource pooling for connections, workers, and memory
- Memory optimization with arena allocation
- Intelligent ML-based task scheduling
- Performance profiling and bottleneck detection
"""

from .resource_pool import ResourcePoolManager, PoolType
from .memory_optimizer import MemoryOptimizer, MemoryArena
from .intelligent_scheduler import IntelligentScheduler, SchedulingStrategy
from .profiler import PerformanceProfiler, ProfilerMode

__all__ = [
    'ResourcePoolManager',
    'PoolType',
    'MemoryOptimizer',
    'MemoryArena',
    'IntelligentScheduler',
    'SchedulingStrategy',
    'PerformanceProfiler',
    'ProfilerMode',
]

__version__ = '1.0.0'
