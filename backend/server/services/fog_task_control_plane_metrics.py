"""
Lightweight metrics registry for the fog task control plane.

Collection stays here; transport/rendering stays in routes or exporters.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


class FogTaskControlPlaneMetrics:
    """In-process counter registry with stable metric names."""

    def __init__(self, counter_names: Iterable[str]) -> None:
        self._counter_names = tuple(counter_names)
        self._counters = Counter({name: 0 for name in self._counter_names})

    def bump(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def snapshot(self) -> dict[str, Any]:
        return dict(self._counters)

    def reset(self) -> None:
        self._counters = Counter({name: 0 for name in self._counter_names})
