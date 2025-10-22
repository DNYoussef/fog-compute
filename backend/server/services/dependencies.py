"""
Service Dependency Management
Handles dependency graph resolution, topological sorting, and circular dependency detection
"""
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """Service types in the FOG Compute platform"""
    DAO = "dao"
    SCHEDULER = "scheduler"
    EDGE = "edge"
    HARVEST = "harvest"
    ONION = "onion"
    VPN_COORDINATOR = "vpn_coordinator"
    FOG_COORDINATOR = "fog_coordinator"
    P2P = "p2p"
    BETANET = "betanet"
    BITCHAT = "bitchat"


@dataclass
class ServiceNode:
    """Represents a service node in the dependency graph"""
    name: str
    service_type: ServiceType
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    optional_dependencies: Set[str] = field(default_factory=set)

    def add_dependency(self, dependency: str, optional: bool = False) -> None:
        """Add a dependency to this service"""
        if optional:
            self.optional_dependencies.add(dependency)
        else:
            self.dependencies.add(dependency)

    def add_dependent(self, dependent: str) -> None:
        """Add a dependent service"""
        self.dependents.add(dependent)


class DependencyGraph:
    """
    Manages service dependency graph
    Provides topological sorting, circular dependency detection, and startup order
    """

    def __init__(self):
        self.nodes: Dict[str, ServiceNode] = {}
        self._startup_order: Optional[List[str]] = None
        self._shutdown_order: Optional[List[str]] = None

    def add_service(
        self,
        name: str,
        service_type: ServiceType,
        dependencies: Optional[List[str]] = None,
        optional_dependencies: Optional[List[str]] = None
    ) -> None:
        """Add a service to the dependency graph"""
        if name in self.nodes:
            logger.warning(f"Service {name} already exists in dependency graph")
            return

        node = ServiceNode(name=name, service_type=service_type)

        # Add dependencies
        if dependencies:
            for dep in dependencies:
                node.add_dependency(dep, optional=False)

        if optional_dependencies:
            for dep in optional_dependencies:
                node.add_dependency(dep, optional=True)

        self.nodes[name] = node

        # Update dependents
        for dep in node.dependencies | node.optional_dependencies:
            if dep in self.nodes:
                self.nodes[dep].add_dependent(name)

        # Invalidate cached orders
        self._startup_order = None
        self._shutdown_order = None

    def get_dependencies(self, service_name: str) -> Set[str]:
        """Get all dependencies for a service"""
        if service_name not in self.nodes:
            return set()
        return self.nodes[service_name].dependencies

    def get_optional_dependencies(self, service_name: str) -> Set[str]:
        """Get optional dependencies for a service"""
        if service_name not in self.nodes:
            return set()
        return self.nodes[service_name].optional_dependencies

    def get_dependents(self, service_name: str) -> Set[str]:
        """Get all services that depend on this service"""
        if service_name not in self.nodes:
            return set()
        return self.nodes[service_name].dependents

    def detect_circular_dependencies(self) -> Optional[List[str]]:
        """
        Detect circular dependencies in the graph
        Returns the cycle path if found, None otherwise
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            if node in self.nodes:
                for dep in self.nodes[node].dependencies:
                    if dep not in visited:
                        cycle = dfs(dep, path.copy())
                        if cycle:
                            return cycle
                    elif dep in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(dep)
                        return path[cycle_start:] + [dep]

            rec_stack.remove(node)
            return None

        for node in self.nodes:
            if node not in visited:
                cycle = dfs(node, [])
                if cycle:
                    return cycle

        return None

    def topological_sort(self) -> List[str]:
        """
        Perform topological sort to determine startup order
        Services with no dependencies start first
        """
        # Check for circular dependencies
        cycle = self.detect_circular_dependencies()
        if cycle:
            raise ValueError(f"Circular dependency detected: {' -> '.join(cycle)}")

        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {name: 0 for name in self.nodes}

        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.name] += 1

        # Queue for nodes with no dependencies
        queue: List[str] = [name for name, degree in in_degree.items() if degree == 0]
        result: List[str] = []

        while queue:
            # Process nodes in alphabetical order for deterministic results
            queue.sort()
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependents
            if current in self.nodes:
                for dependent in self.nodes[current].dependents:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(self.nodes):
            missing = set(self.nodes.keys()) - set(result)
            raise ValueError(f"Unable to resolve dependencies for: {missing}")

        return result

    def get_startup_order(self) -> List[str]:
        """Get the correct startup order for services"""
        if self._startup_order is None:
            self._startup_order = self.topological_sort()
        return self._startup_order

    def get_shutdown_order(self) -> List[str]:
        """
        Get the correct shutdown order for services
        Reverse of startup order (dependents shutdown before dependencies)
        """
        if self._shutdown_order is None:
            self._shutdown_order = list(reversed(self.get_startup_order()))
        return self._shutdown_order

    def get_service_layer(self, service_name: str) -> int:
        """
        Get the layer number of a service in the dependency graph
        Layer 0 = no dependencies, Layer N = depends on services in Layer N-1
        """
        if service_name not in self.nodes:
            return -1

        visited: Set[str] = set()

        def get_depth(node: str) -> int:
            if node in visited:
                return 0
            visited.add(node)

            if node not in self.nodes:
                return 0

            deps = self.nodes[node].dependencies
            if not deps:
                return 0

            return 1 + max(get_depth(dep) for dep in deps if dep in self.nodes)

        return get_depth(service_name)

    def visualize(self) -> str:
        """Generate a text visualization of the dependency graph"""
        lines = ["Service Dependency Graph:", "=" * 50]

        # Group services by layer
        layers: Dict[int, List[str]] = {}
        for service in self.nodes:
            layer = self.get_service_layer(service)
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(service)

        # Print by layer
        for layer in sorted(layers.keys()):
            lines.append(f"\nLayer {layer} (Startup Priority):")
            for service in sorted(layers[layer]):
                node = self.nodes[service]
                deps = f" <- {', '.join(sorted(node.dependencies))}" if node.dependencies else ""
                opt_deps = f" [optional: {', '.join(sorted(node.optional_dependencies))}]" if node.optional_dependencies else ""
                lines.append(f"  • {service}{deps}{opt_deps}")

        return "\n".join(lines)


def create_default_dependency_graph() -> DependencyGraph:
    """
    Create the default dependency graph for FOG Compute services

    Dependency hierarchy:
    - Layer 0: DAO (no dependencies)
    - Layer 1: Scheduler, Edge, Harvest (depend on DAO)
    - Layer 2: Onion, FOG Coordinator (depend on Layer 1)
    - Layer 3: VPN Coordinator, P2P (depend on Layer 2)
    - Layer 4: Betanet, BitChat (depend on P2P)
    """
    graph = DependencyGraph()

    # Layer 0: Core services with no dependencies
    graph.add_service(
        name="dao",
        service_type=ServiceType.DAO,
        dependencies=[]
    )

    # Layer 1: Services that depend on core
    graph.add_service(
        name="scheduler",
        service_type=ServiceType.SCHEDULER,
        dependencies=[],
        optional_dependencies=["dao"]  # Scheduler can work without DAO
    )

    graph.add_service(
        name="edge",
        service_type=ServiceType.EDGE,
        dependencies=[],
        optional_dependencies=["dao"]
    )

    graph.add_service(
        name="harvest",
        service_type=ServiceType.HARVEST,
        dependencies=["edge"]  # Harvest needs edge manager
    )

    # Layer 2: Network infrastructure
    graph.add_service(
        name="fog_coordinator",
        service_type=ServiceType.FOG_COORDINATOR,
        dependencies=[]
    )

    graph.add_service(
        name="onion",
        service_type=ServiceType.ONION,
        dependencies=["fog_coordinator"]  # Onion routing needs coordinator
    )

    # Layer 3: Advanced networking
    graph.add_service(
        name="vpn_coordinator",
        service_type=ServiceType.VPN_COORDINATOR,
        dependencies=["fog_coordinator", "onion"]
    )

    graph.add_service(
        name="p2p",
        service_type=ServiceType.P2P,
        dependencies=[],
        optional_dependencies=["fog_coordinator"]
    )

    # Layer 4: Application services
    graph.add_service(
        name="betanet",
        service_type=ServiceType.BETANET,
        dependencies=[],
        optional_dependencies=["p2p", "onion"]
    )

    graph.add_service(
        name="bitchat",
        service_type=ServiceType.BITCHAT,
        dependencies=[],
        optional_dependencies=["p2p"]
    )

    return graph


def validate_startup_order(order: List[str], graph: DependencyGraph) -> Tuple[bool, Optional[str]]:
    """
    Validate that a startup order respects all dependencies
    Returns (is_valid, error_message)
    """
    started: Set[str] = set()

    for service in order:
        # Check if all dependencies are already started
        deps = graph.get_dependencies(service)
        missing = deps - started

        if missing:
            return False, f"Service '{service}' started before dependencies: {missing}"

        started.add(service)

    return True, None
