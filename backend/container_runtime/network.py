"""
Fog Network Manager
Handles container networking across fog mesh nodes.

Containers on different physical devices can communicate as if
they were on the same local network - fog handles the routing transparently.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Any
from uuid import uuid4
import ipaddress

from .models import NetworkMode, PortMapping

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Network manager configuration."""
    # Overlay network
    overlay_subnet: str = "10.200.0.0/16"     # Fog mesh overlay network
    service_subnet: str = "10.201.0.0/16"     # Service discovery

    # DNS
    dns_domain: str = "fog.local"              # Internal DNS domain
    dns_port: int = 53

    # Port allocation
    host_port_range_start: int = 30000
    host_port_range_end: int = 32767


@dataclass
class FogNetwork:
    """
    A fog overlay network.

    Spans all nodes in the mesh, providing seamless container connectivity.
    """
    network_id: str = field(default_factory=lambda: f"fognet-{uuid4().hex[:8]}")
    name: str = ""
    subnet: str = "10.200.0.0/24"
    gateway: str = "10.200.0.1"

    # DNS
    dns_enabled: bool = True
    dns_domain: Optional[str] = None

    # Mode
    mode: NetworkMode = NetworkMode.FOG_MESH
    is_default: bool = False

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = field(default_factory=dict)

    # Connected containers
    container_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "network_id": self.network_id,
            "name": self.name,
            "subnet": self.subnet,
            "gateway": self.gateway,
            "dns_enabled": self.dns_enabled,
            "dns_domain": self.dns_domain,
            "mode": self.mode.value,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat(),
            "labels": self.labels,
            "container_count": len(self.container_ids),
        }


@dataclass
class NetworkEndpoint:
    """
    Container endpoint in a network.

    Tracks IP assignment and connectivity for a container.
    """
    endpoint_id: str = field(default_factory=lambda: f"ep-{uuid4().hex[:8]}")
    network_id: str = ""
    container_id: str = ""
    container_name: str = ""

    # Network assignment
    ip_address: str = ""
    mac_address: str = ""

    # DNS
    dns_names: list[str] = field(default_factory=list)  # Includes container name and aliases

    # Port mappings (internal to network)
    exposed_ports: list[int] = field(default_factory=list)

    # Node info (for routing)
    node_id: str = ""
    node_ip: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "endpoint_id": self.endpoint_id,
            "network_id": self.network_id,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "dns_names": self.dns_names,
            "exposed_ports": self.exposed_ports,
            "node_id": self.node_id,
            "node_ip": self.node_ip,
        }


@dataclass
class PortAllocation:
    """Host port allocation for a container."""
    container_id: str
    container_port: int
    host_port: int
    protocol: str = "tcp"
    node_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "container_id": self.container_id,
            "container_port": self.container_port,
            "host_port": self.host_port,
            "protocol": self.protocol,
            "node_id": self.node_id,
        }


@dataclass
class DNSRecord:
    """DNS record for service discovery."""
    name: str                         # Hostname (e.g., "postgres.fog.local")
    record_type: str = "A"            # A, AAAA, CNAME, SRV
    value: str = ""                   # IP address or target
    ttl: int = 60
    container_id: Optional[str] = None
    network_id: Optional[str] = None


class FogNetworkManager:
    """
    Manages container networking across fog mesh.

    Features:
    - Overlay networks spanning all nodes
    - Automatic IP assignment
    - DNS-based service discovery
    - Transparent cross-node routing
    - Host port mapping
    """

    def __init__(self, config: Optional[NetworkConfig] = None):
        """
        Initialize network manager.

        Args:
            config: Network configuration
        """
        self.config = config or NetworkConfig()

        # Networks
        self._networks: dict[str, FogNetwork] = {}
        self._default_network_id: Optional[str] = None

        # Endpoints
        self._endpoints: dict[str, NetworkEndpoint] = {}  # endpoint_id -> endpoint
        self._container_endpoints: dict[str, list[str]] = {}  # container_id -> endpoint_ids

        # IP allocation
        self._ip_allocations: dict[str, dict[str, str]] = {}  # network_id -> {ip -> container_id}
        self._next_ip: dict[str, int] = {}  # network_id -> next IP offset

        # Port allocation
        self._port_allocations: dict[str, PortAllocation] = {}  # "node:port:proto" -> allocation
        self._next_port: dict[str, int] = {}  # node_id -> next port

        # DNS
        self._dns_records: dict[str, DNSRecord] = {}  # name -> record

        # Node info
        self._node_ips: dict[str, str] = {}  # node_id -> node IP

        self._lock = asyncio.Lock()

        # Stats
        self._stats = {
            "networks_created": 0,
            "endpoints_created": 0,
            "dns_records": 0,
        }

        logger.info("FogNetworkManager initialized")

        # Create default fog mesh network
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Construction can happen in sync test/setup contexts with no event loop.
            loop = None

        if loop is not None:
            loop.create_task(self._create_default_network())

    async def _create_default_network(self) -> None:
        """Create the default fog mesh network."""
        try:
            network = await self.create_network(
                name="fog-mesh",
                subnet=self.config.overlay_subnet,
                mode=NetworkMode.FOG_MESH,
                is_default=True,
            )
            self._default_network_id = network.network_id
            logger.info(f"Default fog mesh network created: {network.network_id}")
        except Exception as e:
            logger.error(f"Failed to create default network: {e}")

    def register_node(self, node_id: str, ip_address: str) -> None:
        """Register a node's IP address for routing."""
        self._node_ips[node_id] = ip_address
        self._next_port[node_id] = self.config.host_port_range_start
        logger.debug(f"Registered node {node_id} at {ip_address}")

    def unregister_node(self, node_id: str) -> None:
        """Unregister a node."""
        if node_id in self._node_ips:
            del self._node_ips[node_id]
        if node_id in self._next_port:
            del self._next_port[node_id]

    async def create_network(
        self,
        name: str,
        subnet: Optional[str] = None,
        mode: NetworkMode = NetworkMode.FOG_MESH,
        dns_enabled: bool = True,
        labels: Optional[dict[str, str]] = None,
        is_default: bool = False,
    ) -> FogNetwork:
        """
        Create a new fog network.

        Args:
            name: Network name
            subnet: Network subnet (auto-allocated if None)
            mode: Network mode
            dns_enabled: Enable DNS for this network
            labels: Network labels
            is_default: Set as default network

        Returns:
            Created FogNetwork
        """
        async with self._lock:
            # Check name uniqueness
            for net in self._networks.values():
                if net.name == name:
                    raise ValueError(f"Network '{name}' already exists")

            # Allocate subnet if not provided
            if not subnet:
                subnet = self._allocate_subnet()

            # Parse subnet to get gateway
            net = ipaddress.ip_network(subnet, strict=False)
            gateway = str(list(net.hosts())[0])

            network = FogNetwork(
                name=name,
                subnet=subnet,
                gateway=gateway,
                dns_enabled=dns_enabled,
                dns_domain=f"{name}.{self.config.dns_domain}" if dns_enabled else None,
                mode=mode,
                is_default=is_default,
                labels=labels or {},
            )

            self._networks[network.network_id] = network
            self._ip_allocations[network.network_id] = {}
            self._next_ip[network.network_id] = 2  # Start after gateway

            if is_default:
                self._default_network_id = network.network_id

            self._stats["networks_created"] += 1
            logger.info(f"Created network {network.network_id} ({name}): {subnet}")

            return network

    def _allocate_subnet(self) -> str:
        """Allocate a new subnet for a network."""
        # Simple allocation - increment third octet
        base = ipaddress.ip_network(self.config.overlay_subnet)
        used_count = len(self._networks)
        new_net = ipaddress.ip_network(f"10.200.{used_count + 1}.0/24")
        return str(new_net)

    def get_network(self, network_id: str) -> Optional[FogNetwork]:
        """Get network by ID."""
        return self._networks.get(network_id)

    def get_network_by_name(self, name: str) -> Optional[FogNetwork]:
        """Get network by name."""
        for network in self._networks.values():
            if network.name == name:
                return network
        return None

    def get_default_network(self) -> Optional[FogNetwork]:
        """Get the default fog mesh network."""
        if self._default_network_id:
            return self._networks.get(self._default_network_id)
        return None

    def list_networks(self) -> list[FogNetwork]:
        """List all networks."""
        return list(self._networks.values())

    async def delete_network(self, network_id: str, force: bool = False) -> bool:
        """Delete a network."""
        async with self._lock:
            network = self._networks.get(network_id)
            if not network:
                return False

            if network.is_default and not force:
                return False

            if network.container_ids and not force:
                return False

            # Clean up
            if network_id in self._ip_allocations:
                del self._ip_allocations[network_id]
            if network_id in self._next_ip:
                del self._next_ip[network_id]

            del self._networks[network_id]
            logger.info(f"Deleted network {network_id}")
            return True

    async def connect_container(
        self,
        container_id: str,
        container_name: str,
        node_id: str,
        network_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        aliases: Optional[list[str]] = None,
    ) -> NetworkEndpoint:
        """
        Connect a container to a network.

        Args:
            container_id: Container ID
            container_name: Container name
            node_id: Node hosting the container
            network_id: Network to connect to (default if None)
            ip_address: Specific IP address (auto-allocated if None)
            aliases: DNS aliases for the container

        Returns:
            NetworkEndpoint for the container
        """
        async with self._lock:
            # Use default network if not specified
            if not network_id:
                network_id = self._default_network_id

            if not network_id:
                raise ValueError("No network specified and no default network available")

            network = self._networks.get(network_id)
            if not network:
                raise ValueError(f"Network {network_id} not found")

            # Allocate IP if not provided
            if not ip_address:
                ip_address = self._allocate_ip(network_id)

            if not ip_address:
                raise ValueError("Failed to allocate IP address")

            # Generate MAC address
            mac_address = self._generate_mac()

            # Create endpoint
            endpoint = NetworkEndpoint(
                network_id=network_id,
                container_id=container_id,
                container_name=container_name,
                ip_address=ip_address,
                mac_address=mac_address,
                node_id=node_id,
                node_ip=self._node_ips.get(node_id, ""),
            )

            # Set up DNS names
            endpoint.dns_names = [container_name]
            if aliases:
                endpoint.dns_names.extend(aliases)

            self._endpoints[endpoint.endpoint_id] = endpoint

            if container_id not in self._container_endpoints:
                self._container_endpoints[container_id] = []
            self._container_endpoints[container_id].append(endpoint.endpoint_id)

            network.container_ids.append(container_id)

            # Create DNS records
            if network.dns_enabled:
                await self._create_dns_records(endpoint, network)

            self._stats["endpoints_created"] += 1
            logger.info(
                f"Connected container {container_id} to network {network.name} "
                f"at {ip_address}"
            )

            return endpoint

    def _allocate_ip(self, network_id: str) -> Optional[str]:
        """Allocate an IP address from a network's pool."""
        if network_id not in self._ip_allocations:
            return None

        network = self._networks.get(network_id)
        if not network:
            return None

        net = ipaddress.ip_network(network.subnet, strict=False)
        hosts = list(net.hosts())

        next_offset = self._next_ip.get(network_id, 2)

        while next_offset < len(hosts):
            ip = str(hosts[next_offset])
            if ip not in self._ip_allocations[network_id]:
                self._ip_allocations[network_id][ip] = ""  # Reserved
                self._next_ip[network_id] = next_offset + 1
                return ip
            next_offset += 1

        return None

    def _generate_mac(self) -> str:
        """Generate a random MAC address in fog range."""
        import random
        mac = [0x02, 0x46, 0x6f, 0x67,  # "Fog" prefix
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(f'{b:02x}' for b in mac)

    async def _create_dns_records(
        self,
        endpoint: NetworkEndpoint,
        network: FogNetwork
    ) -> None:
        """Create DNS records for a container."""
        for name in endpoint.dns_names:
            # A record for container name
            fqdn = f"{name}.{network.dns_domain}"
            record = DNSRecord(
                name=fqdn,
                record_type="A",
                value=endpoint.ip_address,
                container_id=endpoint.container_id,
                network_id=network.network_id,
            )
            self._dns_records[fqdn] = record
            self._stats["dns_records"] += 1

    async def disconnect_container(
        self,
        container_id: str,
        network_id: Optional[str] = None
    ) -> bool:
        """
        Disconnect a container from a network.

        Args:
            container_id: Container to disconnect
            network_id: Network to disconnect from (all if None)

        Returns:
            True if disconnected successfully
        """
        async with self._lock:
            endpoint_ids = self._container_endpoints.get(container_id, [])

            for ep_id in list(endpoint_ids):
                endpoint = self._endpoints.get(ep_id)
                if not endpoint:
                    continue

                if network_id and endpoint.network_id != network_id:
                    continue

                # Remove from network
                network = self._networks.get(endpoint.network_id)
                if network and container_id in network.container_ids:
                    network.container_ids.remove(container_id)

                # Release IP
                if endpoint.network_id in self._ip_allocations:
                    if endpoint.ip_address in self._ip_allocations[endpoint.network_id]:
                        del self._ip_allocations[endpoint.network_id][endpoint.ip_address]

                # Remove DNS records
                for name in endpoint.dns_names:
                    if network and network.dns_domain:
                        fqdn = f"{name}.{network.dns_domain}"
                        if fqdn in self._dns_records:
                            del self._dns_records[fqdn]

                # Clean up
                del self._endpoints[ep_id]
                endpoint_ids.remove(ep_id)

            if not endpoint_ids and container_id in self._container_endpoints:
                del self._container_endpoints[container_id]

            logger.info(f"Disconnected container {container_id}")
            return True

    async def allocate_host_port(
        self,
        port_mapping: PortMapping,
        container_id: str,
        node_id: str
    ) -> int:
        """
        Allocate a host port for a container port mapping.

        Args:
            port_mapping: Requested port mapping
            container_id: Container ID
            node_id: Node hosting the container

        Returns:
            Allocated host port
        """
        async with self._lock:
            # If specific host port requested, try to use it
            if port_mapping.host_port:
                key = f"{node_id}:{port_mapping.host_port}:{port_mapping.protocol}"
                if key not in self._port_allocations:
                    allocation = PortAllocation(
                        container_id=container_id,
                        container_port=port_mapping.container_port,
                        host_port=port_mapping.host_port,
                        protocol=port_mapping.protocol,
                        node_id=node_id,
                    )
                    self._port_allocations[key] = allocation
                    return port_mapping.host_port
                raise ValueError(f"Port {port_mapping.host_port} already in use")

            # Auto-allocate port
            if node_id not in self._next_port:
                self._next_port[node_id] = self.config.host_port_range_start

            host_port = self._next_port[node_id]
            while host_port <= self.config.host_port_range_end:
                key = f"{node_id}:{host_port}:{port_mapping.protocol}"
                if key not in self._port_allocations:
                    allocation = PortAllocation(
                        container_id=container_id,
                        container_port=port_mapping.container_port,
                        host_port=host_port,
                        protocol=port_mapping.protocol,
                        node_id=node_id,
                    )
                    self._port_allocations[key] = allocation
                    self._next_port[node_id] = host_port + 1
                    return host_port
                host_port += 1

            raise ValueError("No available ports")

    def release_host_ports(self, container_id: str) -> None:
        """Release all host ports for a container."""
        keys_to_remove = [
            key for key, alloc in self._port_allocations.items()
            if alloc.container_id == container_id
        ]
        for key in keys_to_remove:
            del self._port_allocations[key]

    def resolve_dns(self, name: str) -> Optional[str]:
        """Resolve a DNS name to an IP address."""
        record = self._dns_records.get(name)
        if record:
            return record.value
        return None

    def get_routing_info(
        self,
        source_container_id: str,
        target_address: str
    ) -> Optional[dict[str, Any]]:
        """
        Get routing information for container-to-container communication.

        Args:
            source_container_id: Source container
            target_address: Target IP or hostname

        Returns:
            Routing information for the network layer
        """
        # Try DNS resolution first
        target_ip = target_address
        if not target_address[0].isdigit():
            resolved = self.resolve_dns(target_address)
            if resolved:
                target_ip = resolved
            else:
                return None

        # Find target endpoint
        for endpoint in self._endpoints.values():
            if endpoint.ip_address == target_ip:
                # Get source endpoint
                source_endpoints = self._container_endpoints.get(source_container_id, [])
                source_ep = None
                for ep_id in source_endpoints:
                    ep = self._endpoints.get(ep_id)
                    if ep and ep.network_id == endpoint.network_id:
                        source_ep = ep
                        break

                if not source_ep:
                    return None

                return {
                    "target_ip": target_ip,
                    "target_node_id": endpoint.node_id,
                    "target_node_ip": endpoint.node_ip,
                    "same_node": source_ep.node_id == endpoint.node_id,
                    "network_id": endpoint.network_id,
                }

        return None

    def get_endpoint(self, container_id: str, network_id: Optional[str] = None) -> Optional[NetworkEndpoint]:
        """Get endpoint for a container."""
        endpoint_ids = self._container_endpoints.get(container_id, [])
        for ep_id in endpoint_ids:
            endpoint = self._endpoints.get(ep_id)
            if endpoint:
                if network_id is None or endpoint.network_id == network_id:
                    return endpoint
        return None

    def get_container_ip(self, container_id: str, network_id: Optional[str] = None) -> Optional[str]:
        """Get container's IP address."""
        endpoint = self.get_endpoint(container_id, network_id)
        return endpoint.ip_address if endpoint else None

    def get_stats(self) -> dict[str, Any]:
        """Get network manager statistics."""
        return {
            **self._stats,
            "total_networks": len(self._networks),
            "total_endpoints": len(self._endpoints),
            "total_dns_records": len(self._dns_records),
            "total_port_allocations": len(self._port_allocations),
            "registered_nodes": len(self._node_ips),
        }
