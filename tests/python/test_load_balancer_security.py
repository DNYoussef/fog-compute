from dataclasses import dataclass

from fog.load_balancer import LoadBalancer, LoadBalancingAlgorithm


@dataclass
class Node:
    node_id: str
    active_tasks: int = 0
    cpu_usage_percent: float = 0.0


def test_consistent_hash_uses_stable_node_identity():
    nodes = [Node("alpha"), Node("bravo"), Node("charlie")]
    balancer = LoadBalancer(
        algorithm=LoadBalancingAlgorithm.CONSISTENT_HASH,
        enable_circuit_breaker=False,
        enable_auto_scaling=False,
    )

    first = balancer.select_node(nodes, session_id="customer-42")
    second = balancer.select_node(nodes, session_id="customer-42")

    assert first.node_id == second.node_id


def test_consistent_hash_minimizes_remap_when_node_is_added():
    base_nodes = [Node("alpha"), Node("bravo"), Node("charlie")]
    expanded_nodes = base_nodes + [Node("delta")]
    keys = [f"customer-{idx}" for idx in range(200)]
    balancer = LoadBalancer(
        algorithm=LoadBalancingAlgorithm.CONSISTENT_HASH,
        enable_circuit_breaker=False,
        enable_auto_scaling=False,
    )

    before = {
        key: balancer.select_node(base_nodes, session_id=key).node_id
        for key in keys
    }
    balancer.sticky_sessions.clear()
    after = {
        key: balancer.select_node(expanded_nodes, session_id=key).node_id
        for key in keys
    }

    remap_ratio = sum(before[key] != after[key] for key in keys) / len(keys)
    assert remap_ratio < 0.45
