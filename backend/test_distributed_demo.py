"""
Demo: Distributed Container Runtime across Fog Mesh

This demonstrates how containers are transparently distributed across
family devices without the application knowing about the fog network.
"""
import sys
import asyncio
sys.path.insert(0, '.')

from container_runtime.models import (
    Container, ContainerSpec, ContainerStatus, VolumeMount, VolumeType,
    PortMapping, ResourceLimits, NetworkMode
)
from container_runtime.scheduler import FogScheduler, FogNode, PlacementStrategy
from container_runtime.storage import DistributedVolumeManager, VolumeType
from container_runtime.network import FogNetworkManager


async def demo_distributed_containers():
    """
    Demonstrate how fog app runs as a standard container
    while fog network handles distribution transparently.
    """
    print("=" * 60)
    print("FOG BURST: Distributed Container Runtime Demo")
    print("=" * 60)
    print()

    # Initialize the three runtime components
    scheduler = FogScheduler()
    volume_manager = DistributedVolumeManager()
    network_manager = FogNetworkManager()

    # =========================================================================
    # STEP 1: Register family fog devices
    # =========================================================================
    print("STEP 1: Registering fog mesh nodes (family devices)")
    print("-" * 50)

    devices = [
        # (hostname, ip, cpu_cores, memory_mb, disk_mb, device_type)
        ("desktop-david", "192.168.1.10", 8, 32768, 512000, "desktop"),
        ("laptop-work", "192.168.1.11", 4, 16384, 256000, "laptop"),
        ("media-server", "192.168.1.12", 4, 8192, 2048000, "server"),
        ("phone-david", "192.168.1.13", 2, 4096, 64000, "phone"),
        ("tablet-kids", "192.168.1.14", 2, 4096, 128000, "tablet"),
        ("rpi-garage", "192.168.1.15", 1, 1024, 32000, "raspberry-pi"),
    ]

    for hostname, ip, cores, mem, disk, dev_type in devices:
        node = FogNode(
            node_id=f"node-{hostname}",
            hostname=hostname,
            cpu_cores=cores,
            memory_mb=mem,
            disk_mb=disk,
            device_type=dev_type,
        )
        scheduler.register_node(node)
        volume_manager.register_node_storage(f"node-{hostname}", disk, 0)
        network_manager.register_node(f"node-{hostname}", ip)
        print(f"  + {hostname}: {cores} CPU, {mem // 1024}GB RAM, {disk // 1024}GB disk")

    stats = scheduler.get_stats()
    print()
    print(f"Fog mesh total: {stats['total_cpu_cores']} CPU cores, "
          f"{stats['total_memory_mb'] // 1024}GB RAM")
    print()

    # =========================================================================
    # STEP 2: Create fog mesh network
    # =========================================================================
    print("STEP 2: Creating fog mesh overlay network")
    print("-" * 50)

    network = await network_manager.create_network(
        name="fog-app-mesh",
        dns_enabled=True,
    )
    print(f"  Network: {network.name}")
    print(f"  Subnet: {network.subnet}")
    print(f"  Gateway: {network.gateway}")
    print(f"  DNS domain: {network.dns_domain}")
    print()

    # =========================================================================
    # STEP 3: Create distributed volumes
    # =========================================================================
    print("STEP 3: Creating distributed volumes")
    print("-" * 50)

    # Main data volume - replicated across 2 nodes for redundancy
    data_vol = await volume_manager.create_volume(
        name="fog-app-data",
        volume_type=VolumeType.DISTRIBUTED,
        size_mb=10240,
        replication_factor=2,
        consistency_mode="eventual",
    )
    print(f"  Volume: {data_vol.name} ({data_vol.size_mb}MB)")
    print(f"    Type: {data_vol.volume_type.value}")
    print(f"    Primary: {data_vol.primary_node_id}")
    print(f"    Replicas: {data_vol.replica_node_ids}")

    # Database volume - strong consistency
    db_vol = await volume_manager.create_volume(
        name="postgres-data",
        volume_type=VolumeType.DISTRIBUTED,
        size_mb=5120,
        replication_factor=2,
        consistency_mode="strong",
    )
    print(f"  Volume: {db_vol.name} ({db_vol.size_mb}MB)")
    print(f"    Primary: {db_vol.primary_node_id}")
    print()

    # =========================================================================
    # STEP 4: Deploy containers (transparent to fog!)
    # =========================================================================
    print("STEP 4: Deploying containers (fog handles placement)")
    print("-" * 50)

    # This is the key insight: fog app is deployed as a STANDARD container
    # It has NO fog-specific code - fog handles distribution transparently!

    containers = []

    # Deploy PostgreSQL
    db_spec = ContainerSpec(
        image="postgres:15",
        name="db",
        environment={
            "POSTGRES_USER": "lifeos",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_DB": "lifeos",
        },
        resources=ResourceLimits(cpu_cores=1.0, memory_mb=2048),
        volumes=[VolumeMount(
            source="postgres-data",
            target="/var/lib/postgresql/data",
            volume_type=VolumeType.DISTRIBUTED,
        )],
        ports=[PortMapping(container_port=5432)],
    )
    db_container = await scheduler.submit_container(db_spec)
    containers.append(db_container)

    # Deploy Redis
    redis_spec = ContainerSpec(
        image="redis:7",
        name="cache",
        resources=ResourceLimits(cpu_cores=0.5, memory_mb=512),
        ports=[PortMapping(container_port=6379)],
    )
    redis_container = await scheduler.submit_container(redis_spec)
    containers.append(redis_container)

    # Deploy ChromaDB (vector store)
    chroma_spec = ContainerSpec(
        image="chromadb/chroma",
        name="vectordb",
        resources=ResourceLimits(cpu_cores=1.0, memory_mb=1024),
        ports=[PortMapping(container_port=8000)],
    )
    chroma_container = await scheduler.submit_container(chroma_spec)
    containers.append(chroma_container)

    # Deploy fog app itself!
    fog_app_spec = ContainerSpec(
        image="fog-app:latest",
        name="fog-app",
        environment={
            # These use DNS names that resolve within the fog mesh!
            "DATABASE_URL": "postgresql://lifeos:secret@db.fog-app-mesh.fog.local:5432/lifeos",
            "REDIS_URL": "redis://cache.fog-app-mesh.fog.local:6379",
            "CHROMA_URL": "http://vectordb.fog-app-mesh.fog.local:8000",
        },
        resources=ResourceLimits(cpu_cores=2.0, memory_mb=4096),
        volumes=[VolumeMount(
            source="fog-app-data",
            target="/app/data",
            volume_type=VolumeType.DISTRIBUTED,
        )],
        ports=[
            PortMapping(container_port=3000),  # Frontend
            PortMapping(container_port=8000),  # Backend API
        ],
    )
    fog_app_container = await scheduler.submit_container(fog_app_spec)
    containers.append(fog_app_container)

    # Let scheduler place all containers
    await scheduler._process_pending()

    print("Container placement (fog scheduler decisions):")
    for c in containers:
        node = scheduler._nodes.get(c.node_id)
        device = node.device_type if node else "unknown"
        print(f"  {c.name:12} -> {c.node_id} ({device})")
    print()

    # =========================================================================
    # STEP 5: Connect containers to network
    # =========================================================================
    print("STEP 5: Connecting containers to fog mesh network")
    print("-" * 50)

    for container in containers:
        if container.node_id:
            endpoint = await network_manager.connect_container(
                container.container_id,
                container.name,
                container.node_id,
                network.network_id,
            )
            print(f"  {container.name:12} -> {endpoint.ip_address}")
    print()

    # =========================================================================
    # STEP 6: Demonstrate cross-node communication
    # =========================================================================
    print("STEP 6: Cross-node routing (transparent to containers)")
    print("-" * 50)

    # fog app connects to DB using DNS name - fog routes it automatically
    fog_app_ep = network_manager.get_endpoint(fog_app_container.container_id)
    db_ep = network_manager.get_endpoint(db_container.container_id)

    if fog_app_ep and db_ep:
        routing = network_manager.get_routing_info(
            fog_app_container.container_id,
            db_ep.ip_address
        )

        print(f"  fog-app ({fog_app_ep.node_id}) -> db ({db_ep.node_id})")
        if routing:
            if routing["same_node"]:
                print("    Route: LOCAL (same physical device)")
            else:
                print(f"    Route: MESH -> {routing['target_node_ip']}")
    print()

    # =========================================================================
    # FINAL: Show cluster status
    # =========================================================================
    print("=" * 60)
    print("FOG CLUSTER STATUS")
    print("=" * 60)

    stats = scheduler.get_stats()
    vol_stats = volume_manager.get_stats()
    net_stats = network_manager.get_stats()

    print(f"Nodes: {stats['total_nodes']} ({stats['available_nodes']} available)")
    print(f"Containers: {stats['total_containers']} running")
    print(f"CPU: {stats['cpu_utilization_percent']:.1f}% utilized")
    print(f"Memory: {stats['memory_utilization_percent']:.1f}% utilized")
    print()
    print(f"Volumes: {vol_stats['total_volumes']} "
          f"({vol_stats['distributed_volumes']} distributed)")
    print(f"Storage: {vol_stats['storage_utilization_percent']:.1f}% utilized")
    print()
    print(f"Networks: {net_stats['total_networks']}")
    print(f"Endpoints: {net_stats['total_endpoints']}")
    print(f"DNS records: {net_stats['total_dns_records']}")
    print()
    print("=" * 60)
    print()
    print("KEY INSIGHT:")
    print("fog app runs as a STANDARD container. It connects to services")
    print("using normal DNS names (db.fog-app-mesh.fog.local). The fog")
    print("runtime handles all distribution, replication, and cross-device")
    print("routing TRANSPARENTLY. No fog-specific code in the application!")
    print()

    return True


if __name__ == "__main__":
    result = asyncio.run(demo_distributed_containers())
    print("Demo completed successfully!" if result else "Demo failed!")
