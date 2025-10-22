"""
Advanced Load Balancer for FOG Coordinator

Implements multiple load balancing algorithms:
- Weighted round-robin with health awareness
- Least-connections algorithm
- Response-time-based routing
- Sticky sessions with consistent hashing
- Auto-scaling triggers (CPU >80% → scale up)
"""

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LoadBalancingAlgorithm(Enum):
    """Load balancing algorithm types"""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RESPONSE_TIME = "response_time"
    CONSISTENT_HASH = "consistent_hash"
    RANDOM = "random"


class NodeHealth(Enum):
    """Node health status for circuit breaker"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class CircuitBreaker:
    """
    Circuit breaker for failing nodes.

    After 5 failures, node enters 60s timeout before retry.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before circuit opens
            timeout_seconds: Timeout duration when circuit opens
            success_threshold: Successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold

        # Track failures and timeouts per node
        self.failures: dict[str, int] = defaultdict(int)
        self.successes: dict[str, int] = defaultdict(int)
        self.circuit_open_until: dict[str, datetime] = {}

    def record_success(self, node_id: str):
        """Record successful request"""
        self.failures[node_id] = 0
        self.successes[node_id] += 1

        # Close circuit if enough successes
        if self.successes[node_id] >= self.success_threshold:
            self.circuit_open_until.pop(node_id, None)
            self.successes[node_id] = 0
            logger.info(f"Circuit breaker closed for node {node_id}")

    def record_failure(self, node_id: str):
        """Record failed request"""
        self.failures[node_id] += 1
        self.successes[node_id] = 0

        # Open circuit if threshold reached
        if self.failures[node_id] >= self.failure_threshold:
            timeout_until = datetime.now() + timedelta(seconds=self.timeout_seconds)
            self.circuit_open_until[node_id] = timeout_until
            logger.warning(
                f"Circuit breaker OPENED for node {node_id} "
                f"(failures={self.failures[node_id]}, "
                f"timeout={self.timeout_seconds}s)"
            )

    def is_available(self, node_id: str) -> bool:
        """Check if node is available (circuit closed)"""
        if node_id not in self.circuit_open_until:
            return True

        # Check if timeout expired
        now = datetime.now()
        if now >= self.circuit_open_until[node_id]:
            # Timeout expired, allow retry
            self.circuit_open_until.pop(node_id)
            self.failures[node_id] = 0
            logger.info(f"Circuit breaker HALF-OPEN for node {node_id} (allowing retry)")
            return True

        return False

    def get_status(self, node_id: str) -> NodeHealth:
        """Get node health status"""
        if not self.is_available(node_id):
            return NodeHealth.CIRCUIT_OPEN

        failures = self.failures.get(node_id, 0)
        if failures == 0:
            return NodeHealth.HEALTHY
        elif failures < self.failure_threshold // 2:
            return NodeHealth.DEGRADED
        else:
            return NodeHealth.UNHEALTHY


class LoadBalancer:
    """
    Advanced load balancer with multiple algorithms and auto-scaling.
    """

    def __init__(
        self,
        algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.LEAST_CONNECTIONS,
        enable_circuit_breaker: bool = True,
        enable_auto_scaling: bool = True,
        cpu_scale_up_threshold: float = 80.0,
        cpu_scale_down_threshold: float = 30.0,
    ):
        """
        Initialize load balancer.

        Args:
            algorithm: Default load balancing algorithm
            enable_circuit_breaker: Enable circuit breaker pattern
            enable_auto_scaling: Enable auto-scaling triggers
            cpu_scale_up_threshold: CPU % to trigger scale-up
            cpu_scale_down_threshold: CPU % to trigger scale-down
        """
        self.algorithm = algorithm
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_auto_scaling = enable_auto_scaling
        self.cpu_scale_up_threshold = cpu_scale_up_threshold
        self.cpu_scale_down_threshold = cpu_scale_down_threshold

        # Round-robin state
        self.rr_index = 0

        # Node metrics
        self.node_connections: dict[str, int] = defaultdict(int)
        self.node_response_times: dict[str, list[float]] = defaultdict(list)
        self.node_weights: dict[str, float] = defaultdict(lambda: 1.0)

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

        # Sticky sessions (session_id -> node_id)
        self.sticky_sessions: dict[str, str] = {}

        # Auto-scaling events
        self.scaling_events: list[dict[str, Any]] = []

        logger.info(
            f"LoadBalancer initialized: algorithm={algorithm.value}, "
            f"circuit_breaker={enable_circuit_breaker}, "
            f"auto_scaling={enable_auto_scaling}"
        )

    def select_node(
        self,
        nodes: list[Any],
        algorithm: Optional[LoadBalancingAlgorithm] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Select best node using specified algorithm.

        Args:
            nodes: List of available nodes
            algorithm: Algorithm to use (None = default)
            session_id: Optional session ID for sticky sessions

        Returns:
            Selected node or None
        """
        if not nodes:
            return None

        # Filter unhealthy nodes
        eligible_nodes = self._filter_healthy_nodes(nodes)
        if not eligible_nodes:
            logger.warning("No healthy nodes available")
            return None

        # Check sticky session
        if session_id and session_id in self.sticky_sessions:
            sticky_node_id = self.sticky_sessions[session_id]
            sticky_node = next(
                (n for n in eligible_nodes if n.node_id == sticky_node_id), None
            )
            if sticky_node:
                logger.debug(f"Using sticky session: {session_id} -> {sticky_node_id}")
                return sticky_node

        # Select algorithm
        algo = algorithm or self.algorithm

        # Route to algorithm
        if algo == LoadBalancingAlgorithm.ROUND_ROBIN:
            selected = self._round_robin(eligible_nodes)
        elif algo == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            selected = self._weighted_round_robin(eligible_nodes)
        elif algo == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            selected = self._least_connections(eligible_nodes)
        elif algo == LoadBalancingAlgorithm.RESPONSE_TIME:
            selected = self._response_time_based(eligible_nodes)
        elif algo == LoadBalancingAlgorithm.CONSISTENT_HASH:
            selected = self._consistent_hash(eligible_nodes, session_id or "")
        else:
            # Fallback to round-robin
            selected = self._round_robin(eligible_nodes)

        # Create sticky session if session_id provided
        if selected and session_id:
            self.sticky_sessions[session_id] = selected.node_id

        return selected

    def _filter_healthy_nodes(self, nodes: list[Any]) -> list[Any]:
        """Filter nodes by circuit breaker status"""
        if not self.circuit_breaker:
            return nodes

        healthy = [
            n for n in nodes if self.circuit_breaker.is_available(n.node_id)
        ]

        blocked_count = len(nodes) - len(healthy)
        if blocked_count > 0:
            logger.warning(f"{blocked_count} nodes blocked by circuit breaker")

        return healthy

    def _round_robin(self, nodes: list[Any]) -> Any:
        """Simple round-robin selection"""
        node = nodes[self.rr_index % len(nodes)]
        self.rr_index += 1
        return node

    def _weighted_round_robin(self, nodes: list[Any]) -> Any:
        """Weighted round-robin based on node capacity and health"""
        # Calculate weights based on available capacity
        weights = []
        for node in nodes:
            # Base weight
            weight = self.node_weights.get(node.node_id, 1.0)

            # Adjust by CPU availability
            cpu_available = 100 - node.cpu_usage_percent
            weight *= cpu_available / 100

            # Adjust by health status
            if self.circuit_breaker:
                health = self.circuit_breaker.get_status(node.node_id)
                if health == NodeHealth.DEGRADED:
                    weight *= 0.5
                elif health == NodeHealth.UNHEALTHY:
                    weight *= 0.1

            weights.append(max(weight, 0.1))  # Minimum weight

        # Select based on weights
        total_weight = sum(weights)
        cumulative = 0
        target = (self.rr_index % int(total_weight * 100)) / 100

        for node, weight in zip(nodes, weights):
            cumulative += weight
            if cumulative >= target:
                self.rr_index += 1
                return node

        # Fallback
        return nodes[0]

    def _least_connections(self, nodes: list[Any]) -> Any:
        """Select node with least active connections"""
        return min(
            nodes,
            key=lambda n: (
                self.node_connections.get(n.node_id, 0),
                n.active_tasks,
                n.cpu_usage_percent,
            ),
        )

    def _response_time_based(self, nodes: list[Any]) -> Any:
        """Select node with best average response time"""

        def avg_response_time(node_id: str) -> float:
            times = self.node_response_times.get(node_id, [])
            return sum(times) / len(times) if times else float("inf")

        return min(nodes, key=lambda n: avg_response_time(n.node_id))

    def _consistent_hash(self, nodes: list[Any], key: str) -> Any:
        """Consistent hashing for sticky sessions"""
        if not key:
            return nodes[0]

        # Hash the key
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)

        # Map to node
        node_index = hash_value % len(nodes)
        return nodes[node_index]

    def record_request_start(self, node_id: str):
        """Record request started to node"""
        self.node_connections[node_id] += 1

    def record_request_end(
        self, node_id: str, success: bool, response_time_ms: Optional[float] = None
    ):
        """Record request completed"""
        # Update connection count
        if self.node_connections[node_id] > 0:
            self.node_connections[node_id] -= 1

        # Update circuit breaker
        if self.circuit_breaker:
            if success:
                self.circuit_breaker.record_success(node_id)
            else:
                self.circuit_breaker.record_failure(node_id)

        # Track response time
        if response_time_ms is not None:
            times = self.node_response_times[node_id]
            times.append(response_time_ms)
            # Keep last 100 samples
            if len(times) > 100:
                times.pop(0)

    def check_auto_scaling(self, nodes: list[Any]) -> Optional[dict[str, Any]]:
        """
        Check if auto-scaling is needed.

        Returns:
            Scaling recommendation or None
        """
        if not self.enable_auto_scaling or not nodes:
            return None

        # Calculate average CPU usage
        total_cpu = sum(n.cpu_usage_percent for n in nodes)
        avg_cpu = total_cpu / len(nodes)

        # Check scale-up threshold
        if avg_cpu > self.cpu_scale_up_threshold:
            event = {
                "action": "scale_up",
                "reason": f"High CPU usage ({avg_cpu:.1f}% > {self.cpu_scale_up_threshold}%)",
                "current_nodes": len(nodes),
                "avg_cpu": avg_cpu,
                "timestamp": datetime.now().isoformat(),
            }
            self.scaling_events.append(event)
            logger.warning(f"Auto-scaling: SCALE UP needed - {event['reason']}")
            return event

        # Check scale-down threshold
        if avg_cpu < self.cpu_scale_down_threshold and len(nodes) > 2:
            event = {
                "action": "scale_down",
                "reason": f"Low CPU usage ({avg_cpu:.1f}% < {self.cpu_scale_down_threshold}%)",
                "current_nodes": len(nodes),
                "avg_cpu": avg_cpu,
                "timestamp": datetime.now().isoformat(),
            }
            self.scaling_events.append(event)
            logger.info(f"Auto-scaling: SCALE DOWN possible - {event['reason']}")
            return event

        return None

    def get_node_health(self, node_id: str) -> NodeHealth:
        """Get circuit breaker health status for node"""
        if not self.circuit_breaker:
            return NodeHealth.HEALTHY
        return self.circuit_breaker.get_status(node_id)

    def get_metrics(self) -> dict[str, Any]:
        """Get load balancer metrics"""
        metrics = {
            "algorithm": self.algorithm.value,
            "total_connections": sum(self.node_connections.values()),
            "sticky_sessions": len(self.sticky_sessions),
            "scaling_events": len(self.scaling_events),
            "recent_scaling_events": self.scaling_events[-5:],
        }

        # Circuit breaker stats
        if self.circuit_breaker:
            open_circuits = sum(
                1
                for node_id in self.circuit_breaker.failures.keys()
                if not self.circuit_breaker.is_available(node_id)
            )
            metrics["circuit_breaker"] = {
                "enabled": True,
                "open_circuits": open_circuits,
                "total_failures": sum(self.circuit_breaker.failures.values()),
            }
        else:
            metrics["circuit_breaker"] = {"enabled": False}

        return metrics

    def reset_sticky_session(self, session_id: str):
        """Remove sticky session mapping"""
        self.sticky_sessions.pop(session_id, None)

    def set_node_weight(self, node_id: str, weight: float):
        """Set custom weight for weighted round-robin"""
        self.node_weights[node_id] = max(0.1, min(weight, 10.0))
