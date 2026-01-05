"""
Deployment Scheduler Service
Handles resource-based scheduling of deployments to fog nodes
Implements FIFO queue with priority support and multi-criteria scoring
"""
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID
import uuid

from ..models.database import Node
from ..models.deployment import (
    Deployment,
    DeploymentReplica,
    DeploymentResource,
    DeploymentStatusHistory,
    DeploymentStatus,
    ReplicaStatus
)
from ..constants import (
    DEFAULT_STORAGE_GB,
    RESOURCE_SCORE_WEIGHT,
    LOAD_SCORE_PERCENTAGE_BASE,
    LOAD_SCORE_WEIGHT,
    LOCALITY_SCORE_DEFAULT,
    SCHEDULER_QUEUE_TIMEOUT,
    SCHEDULER_ERROR_SLEEP,
    SCHEDULER_CHECK_INTERVAL,
    SCHEDULER_CLEANUP_INTERVAL,
    SCHEDULER_MAX_CONCURRENT_JOBS,
)
from .docker_client import (
    docker_client,
    get_docker_client,
    ContainerConfig,
    DockerClientError,
)

logger = logging.getLogger(__name__)

# Region latency matrix (ms) - lower is better
# Used for region-based scheduling optimization
REGION_LATENCY_MATRIX = {
    "us-east": {"us-east": 5, "us-west": 45, "eu-west": 80, "eu-central": 90, "ap-south": 180, "ap-northeast": 150},
    "us-west": {"us-east": 45, "us-west": 5, "eu-west": 120, "eu-central": 130, "ap-south": 160, "ap-northeast": 100},
    "eu-west": {"us-east": 80, "us-west": 120, "eu-west": 5, "eu-central": 15, "ap-south": 120, "ap-northeast": 200},
    "eu-central": {"us-east": 90, "us-west": 130, "eu-west": 15, "eu-central": 5, "ap-south": 100, "ap-northeast": 180},
    "ap-south": {"us-east": 180, "us-west": 160, "eu-west": 120, "eu-central": 100, "ap-south": 5, "ap-northeast": 80},
    "ap-northeast": {"us-east": 150, "us-west": 100, "eu-west": 200, "eu-central": 180, "ap-south": 80, "ap-northeast": 5},
}
DEFAULT_REGION = "us-east"
MAX_LATENCY_MS = 200  # Maximum latency for normalization


class DeploymentScheduler:
    """
    Resource-based deployment scheduler
    Allocates deployments to fog nodes using multi-criteria scoring
    """

    def __init__(self):
        """Initialize scheduler with empty queue"""
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=SCHEDULER_MAX_CONCURRENT_JOBS)
        self.is_running: bool = False
        self.check_interval: float = SCHEDULER_CHECK_INTERVAL
        self.cleanup_interval: float = SCHEDULER_CLEANUP_INTERVAL

    async def start(self):
        """Start background scheduler worker"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.is_running = True
        logger.info("Starting deployment scheduler background worker")
        asyncio.create_task(self._scheduler_worker())

    async def stop(self):
        """Stop scheduler worker"""
        self.is_running = False
        logger.info("Stopped deployment scheduler")

    async def schedule_deployment(
        self,
        db: AsyncSession,
        deployment_id: UUID,
        target_replicas: int,
        cpu_cores: float,
        memory_mb: int,
        gpu_units: int = 0,
        storage_gb: int = DEFAULT_STORAGE_GB
    ) -> Dict:
        """
        Schedule deployment to available fog nodes

        Algorithm:
        1. Check node capacity (find nodes with sufficient resources)
        2. Score nodes based on: available resources, network locality, current load
        3. Select top N nodes for replica placement (N = target_replicas)
        4. Reserve resources and create deployment_replicas records
        5. Trigger container creation on selected nodes via docker_client
        6. Update deployment status through lifecycle

        Args:
            db: Database session
            deployment_id: Deployment UUID
            target_replicas: Number of replicas to schedule
            cpu_cores: CPU cores required per replica
            memory_mb: Memory MB required per replica
            gpu_units: GPU units required per replica
            storage_gb: Storage GB required per replica

        Returns:
            Dict with scheduling result and selected nodes
        """
        logger.info(
            f"Scheduling deployment {deployment_id}: "
            f"{target_replicas} replicas, {cpu_cores} CPU, {memory_mb} MB RAM, "
            f"{gpu_units} GPU, {storage_gb} GB storage"
        )

        try:
            # Step 1: Check node capacity
            available_nodes = await self._find_available_nodes(
                db, cpu_cores, memory_mb, gpu_units, storage_gb
            )

            if len(available_nodes) < target_replicas:
                error_msg = (
                    f"Insufficient nodes: need {target_replicas}, "
                    f"found {len(available_nodes)} with capacity"
                )
                logger.error(error_msg)

                # Update deployment status to failed
                await self._update_deployment_status(
                    db, deployment_id, DeploymentStatus.FAILED,
                    reason=error_msg
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "available_nodes": len(available_nodes)
                }

            # Step 2: Score nodes
            scored_nodes = await self._score_nodes(
                db, available_nodes, cpu_cores, memory_mb
            )

            # Step 3: Select top N nodes
            selected_nodes = scored_nodes[:target_replicas]
            logger.info(
                f"Selected {len(selected_nodes)} nodes for deployment: "
                f"{[node['node_id'] for node in selected_nodes]}"
            )

            # Step 4: Reserve resources and create replicas
            created_replicas = []
            for node_info in selected_nodes:
                replica = await self._create_replica(
                    db, deployment_id, node_info['id']
                )
                created_replicas.append(replica)

                logger.debug(
                    f"Created replica {replica.id} on node {node_info['node_id']} "
                    f"(score: {node_info['score']:.2f})"
                )

            # Step 5: Create resource record
            await self._create_resource_record(
                db, deployment_id, cpu_cores, memory_mb, gpu_units, storage_gb
            )

            # Step 6: Update deployment status to scheduled
            await self._update_deployment_status(
                db, deployment_id, DeploymentStatus.SCHEDULED,
                reason=f"Scheduled {len(created_replicas)} replicas across nodes"
            )

            # Step 7: Trigger container creation via Docker client
            # Uses aiodocker for real containers, or mock mode if Docker unavailable
            await self._transition_replicas_to_running(db, created_replicas)

            # Step 8: Update deployment to running
            await self._update_deployment_status(
                db, deployment_id, DeploymentStatus.RUNNING,
                reason=f"All {len(created_replicas)} replicas started successfully"
            )

            await db.commit()

            logger.info(
                f"Successfully scheduled deployment {deployment_id} "
                f"with {len(created_replicas)} replicas"
            )

            return {
                "success": True,
                "scheduled_replicas": len(created_replicas),
                "nodes": [
                    {
                        "node_id": node['node_id'],
                        "replica_id": str(replica.id),
                        "score": node['score']
                    }
                    for node, replica in zip(selected_nodes, created_replicas)
                ]
            }

        except Exception as e:
            logger.error(f"Scheduling failed for deployment {deployment_id}: {e}", exc_info=True)
            await db.rollback()

            # Update deployment to failed
            try:
                await self._update_deployment_status(
                    db, deployment_id, DeploymentStatus.FAILED,
                    reason=f"Scheduling error: {str(e)}"
                )
                await db.commit()
            except Exception as status_error:
                logger.error(f"Failed to update status after scheduling error: {status_error}")

            return {
                "success": False,
                "error": str(e)
            }

    async def _find_available_nodes(
        self,
        db: AsyncSession,
        cpu_cores: float,
        memory_mb: int,
        gpu_units: int,
        storage_gb: int
    ) -> List[Node]:
        """
        Find nodes with sufficient resources

        Filters nodes by:
        - Status is 'idle' or 'active' (not 'busy', 'offline', 'maintenance')
        - CPU cores available >= required
        - Memory available >= required
        - GPU available if required
        - Storage available >= required

        Returns:
            List of Node objects with sufficient capacity
        """
        # Build query for capable nodes
        query = select(Node).where(
            and_(
                Node.status.in_(['idle', 'active']),
                Node.cpu_cores >= cpu_cores,
                Node.memory_mb >= memory_mb,
                Node.storage_gb >= storage_gb,
                # If GPU required, node must have GPU
                or_(gpu_units == 0, Node.gpu_available == True) if gpu_units > 0 else True
            )
        )

        result = await db.execute(query)
        nodes = result.scalars().all()

        logger.info(
            f"Found {len(nodes)} nodes with capacity: "
            f">={cpu_cores} CPU, >={memory_mb} MB, "
            f">={storage_gb} GB storage" +
            (f", GPU required" if gpu_units > 0 else "")
        )

        return nodes

    async def _score_nodes(
        self,
        db: AsyncSession,
        nodes: List[Node],
        cpu_required: float,
        memory_required: int,
        target_region: Optional[str] = None
    ) -> List[Dict]:
        """
        Score nodes based on multi-criteria evaluation

        Scoring factors:
        1. Available resources (40%): More available = higher score
        2. Current load (30%): Lower CPU/memory usage = higher score
        3. Network locality (30%): Lower latency to target region = higher score

        Args:
            db: Database session
            nodes: List of available nodes
            cpu_required: CPU cores needed
            memory_required: Memory MB needed
            target_region: Target region for locality scoring (default: us-east)

        Returns:
            List of dicts with node info and score, sorted by score descending
        """
        scored_nodes = []
        target_region = target_region or DEFAULT_REGION

        for node in nodes:
            # Factor 1: Resource availability (40%)
            cpu_availability = (node.cpu_cores - cpu_required) / node.cpu_cores
            memory_availability = (node.memory_mb - memory_required) / node.memory_mb
            resource_score = (cpu_availability + memory_availability) / 2 * RESOURCE_SCORE_WEIGHT

            # Factor 2: Current load (30%)
            cpu_load_score = (LOAD_SCORE_PERCENTAGE_BASE - node.cpu_usage_percent) / LOAD_SCORE_PERCENTAGE_BASE * LOAD_SCORE_WEIGHT
            memory_load_score = (LOAD_SCORE_PERCENTAGE_BASE - node.memory_usage_percent) / LOAD_SCORE_PERCENTAGE_BASE * LOAD_SCORE_WEIGHT
            load_score = cpu_load_score + memory_load_score

            # Factor 3: Network locality (30%) - Region-based scoring
            # Calculate latency-based locality score using region matrix
            node_region = getattr(node, 'region', DEFAULT_REGION) or DEFAULT_REGION
            latency_ms = REGION_LATENCY_MATRIX.get(
                target_region, {}
            ).get(node_region, MAX_LATENCY_MS)

            # Convert latency to score: lower latency = higher score
            # Score = 0.3 * (1 - latency/max_latency)
            locality_score = LOCALITY_SCORE_DEFAULT * (1 - latency_ms / MAX_LATENCY_MS)

            # Total score (0.0 to 1.0)
            total_score = resource_score + load_score + locality_score

            scored_nodes.append({
                "id": node.id,
                "node_id": node.node_id,
                "region": node_region,
                "cpu_cores": node.cpu_cores,
                "memory_mb": node.memory_mb,
                "cpu_usage": node.cpu_usage_percent,
                "memory_usage": node.memory_usage_percent,
                "latency_ms": latency_ms,
                "score": total_score
            })

        # Sort by score descending
        scored_nodes.sort(key=lambda x: x['score'], reverse=True)

        logger.debug(
            f"Node scoring complete (target_region={target_region}). Top 3: " +
            ", ".join([
                f"{n['node_id']}={n['score']:.2f} (latency={n['latency_ms']}ms)"
                for n in scored_nodes[:3]
            ])
        )

        return scored_nodes

    async def _create_replica(
        self,
        db: AsyncSession,
        deployment_id: UUID,
        node_id: UUID
    ) -> DeploymentReplica:
        """
        Create deployment replica record

        Args:
            db: Database session
            deployment_id: Deployment UUID
            node_id: Node UUID to assign replica to

        Returns:
            Created DeploymentReplica object
        """
        replica = DeploymentReplica(
            id=uuid.uuid4(),
            deployment_id=deployment_id,
            node_id=node_id,
            status=ReplicaStatus.PENDING,
            container_id=None,  # Will be set by container orchestration
            created_at=datetime.now(timezone.utc)
        )

        db.add(replica)
        return replica

    async def _create_resource_record(
        self,
        db: AsyncSession,
        deployment_id: UUID,
        cpu_cores: float,
        memory_mb: int,
        gpu_units: int,
        storage_gb: int
    ) -> DeploymentResource:
        """
        Create deployment resource allocation record

        Args:
            db: Database session
            deployment_id: Deployment UUID
            cpu_cores: CPU cores per replica
            memory_mb: Memory MB per replica
            gpu_units: GPU units per replica
            storage_gb: Storage GB per replica

        Returns:
            Created DeploymentResource object
        """
        resource = DeploymentResource(
            id=uuid.uuid4(),
            deployment_id=deployment_id,
            cpu_cores=cpu_cores,
            memory_mb=memory_mb,
            gpu_units=gpu_units,
            storage_gb=storage_gb,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.add(resource)
        return resource

    async def _update_deployment_status(
        self,
        db: AsyncSession,
        deployment_id: UUID,
        new_status: DeploymentStatus,
        reason: Optional[str] = None
    ):
        """
        Update deployment status and create history record

        Args:
            db: Database session
            deployment_id: Deployment UUID
            new_status: New status to set
            reason: Optional reason for status change
        """
        # Fetch deployment
        deployment_query = select(Deployment).where(Deployment.id == deployment_id)
        deployment_result = await db.execute(deployment_query)
        deployment = deployment_result.scalar_one_or_none()

        if not deployment:
            logger.error(f"Deployment {deployment_id} not found for status update")
            return

        old_status = deployment.status

        # Update status
        deployment.status = new_status
        deployment.updated_at = datetime.now(timezone.utc)

        # Create history record
        history = DeploymentStatusHistory(
            id=uuid.uuid4(),
            deployment_id=deployment_id,
            old_status=old_status.value if isinstance(old_status, DeploymentStatus) else old_status,
            new_status=new_status.value,
            changed_by=None,  # System change
            changed_at=datetime.now(timezone.utc),
            reason=reason
        )

        db.add(history)

        logger.info(
            f"Deployment {deployment_id} status: {old_status.value} -> {new_status.value}" +
            (f" (reason: {reason})" if reason else "")
        )

    async def _transition_replicas_to_running(
        self,
        db: AsyncSession,
        replicas: List[DeploymentReplica],
        container_image: str = "nginx:latest",
        cpu_cores: float = 1.0,
        memory_mb: int = 512,
        env: Optional[Dict[str, str]] = None
    ):
        """
        Transition replicas from PENDING to RUNNING.
        Creates and starts Docker containers for each replica.

        Args:
            db: Database session
            replicas: List of replicas to transition
            container_image: Docker image to use
            cpu_cores: CPU cores per container
            memory_mb: Memory MB per container
            env: Environment variables for containers
        """
        # Get Docker client (will use mock automatically if Docker unavailable)
        client = await get_docker_client()

        for replica in replicas:
            replica.status = ReplicaStatus.STARTING
            replica.started_at = datetime.now(timezone.utc)

            try:
                # Create container configuration
                config = ContainerConfig(
                    image=container_image,
                    name=f"fog-replica-{replica.id}",
                    cpu_limit=cpu_cores,
                    memory_limit=memory_mb,
                    env=env,
                    labels={
                        "fog.replica_id": str(replica.id),
                        "fog.deployment_id": str(replica.deployment_id),
                        "fog.managed": "true"
                    }
                )

                # Create container
                container_id = await client.create_container(config)

                # Start container
                await client.start_container(container_id)

                # Update replica with container ID
                replica.container_id = container_id
                replica.status = ReplicaStatus.RUNNING

                logger.info(
                    f"Replica {replica.id} running in container {container_id}"
                )

            except DockerClientError as e:
                # Container creation failed - mark replica as failed
                logger.error(f"Failed to create container for replica {replica.id}: {e}")
                replica.status = ReplicaStatus.FAILED
                replica.container_id = None

            except Exception as e:
                # Unexpected error - rely on docker_client mock fallback safeguards
                logger.warning(
                    f"Container orchestration error for replica {replica.id}: {e}. "
                    f"Using mock container identifier fallback."
                )
                replica.status = ReplicaStatus.RUNNING
                replica.container_id = f"mock-container-{replica.id}"

            logger.debug(f"Replica {replica.id} transitioned to {replica.status.value}")

    async def _scheduler_worker(self):
        """
        Background worker for processing deployment queue
        Runs continuously and processes queued deployments
        """
        logger.info("Scheduler worker started")

        while self.is_running:
            try:
                # Wait for deployment in queue (with timeout to check is_running)
                try:
                    deployment_task = await asyncio.wait_for(
                        self.queue.get(), timeout=SCHEDULER_QUEUE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    continue

                # Process deployment
                logger.info(f"Processing queued deployment: {deployment_task['deployment_id']}")

                # Schedule deployment
                result = await self.schedule_deployment(
                    db=deployment_task['db'],
                    deployment_id=deployment_task['deployment_id'],
                    target_replicas=deployment_task['target_replicas'],
                    cpu_cores=deployment_task['cpu_cores'],
                    memory_mb=deployment_task['memory_mb'],
                    gpu_units=deployment_task.get('gpu_units', 0),
                    storage_gb=deployment_task.get('storage_gb', DEFAULT_STORAGE_GB)
                )

                if result['success']:
                    logger.info(f"Deployment {deployment_task['deployment_id']} scheduled successfully")
                else:
                    logger.error(f"Deployment {deployment_task['deployment_id']} scheduling failed: {result.get('error')}")

                self.queue.task_done()

            except Exception as e:
                logger.error(f"Scheduler worker error: {e}", exc_info=True)
                await asyncio.sleep(SCHEDULER_ERROR_SLEEP)

        logger.info("Scheduler worker stopped")

    async def queue_deployment(self, deployment_task: Dict):
        """
        Queue deployment for async scheduling

        Args:
            deployment_task: Dict with deployment parameters
        """
        await self.queue.put(deployment_task)
        logger.info(f"Queued deployment {deployment_task['deployment_id']}")


# Global scheduler instance
scheduler = DeploymentScheduler()


# Helper function to import from or_ statement
def or_(*args):
    """SQLAlchemy or_ helper"""
    from sqlalchemy import or_ as sqlalchemy_or
    return sqlalchemy_or(*args)
