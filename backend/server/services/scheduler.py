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

from ..constants import (
    SCHEDULER_DEFAULT_STORAGE_GB,
    SCHEDULER_QUEUE_WAIT_TIMEOUT_SECONDS,
    SCHEDULER_WORKER_ERROR_SLEEP_SECONDS,
)
from ..models.database import Node
from ..models.deployment import (
    Deployment,
    DeploymentReplica,
    DeploymentResource,
    DeploymentStatusHistory,
    DeploymentStatus,
    ReplicaStatus
)

logger = logging.getLogger(__name__)


class DeploymentScheduler:
    """
    Resource-based deployment scheduler
    Allocates deployments to fog nodes using multi-criteria scoring
    """

    def __init__(self):
        """Initialize scheduler with empty queue"""
        self.queue: asyncio.Queue = asyncio.Queue()
        self.is_running: bool = False

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
        storage_gb: int = SCHEDULER_DEFAULT_STORAGE_GB
    ) -> Dict:
        """
        Schedule deployment to available fog nodes

        Algorithm:
        1. Check node capacity (find nodes with sufficient resources)
        2. Score nodes based on: available resources, network locality, current load
        3. Select top N nodes for replica placement (N = target_replicas)
        4. Reserve resources and create deployment_replicas records
        5. Trigger container creation on selected nodes (stub for now)
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

            # Step 7: Trigger container creation (stub)
            # TODO: Implement actual container orchestration
            # For now, just transition replicas to RUNNING
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
        memory_required: int
    ) -> List[Dict]:
        """
        Score nodes based on multi-criteria evaluation

        Scoring factors:
        1. Available resources (40%): More available = higher score
        2. Current load (30%): Lower CPU/memory usage = higher score
        3. Network locality (30%): Same region = higher score (future enhancement)

        Returns:
            List of dicts with node info and score, sorted by score descending
        """
        scored_nodes = []

        for node in nodes:
            # Factor 1: Resource availability (40%)
            cpu_availability = (node.cpu_cores - cpu_required) / node.cpu_cores
            memory_availability = (node.memory_mb - memory_required) / node.memory_mb
            resource_score = (cpu_availability + memory_availability) / 2 * 0.4

            # Factor 2: Current load (30%)
            cpu_load_score = (100 - node.cpu_usage_percent) / 100 * 0.15
            memory_load_score = (100 - node.memory_usage_percent) / 100 * 0.15
            load_score = cpu_load_score + memory_load_score

            # Factor 3: Network locality (30%)
            # TODO: Implement region-based scoring
            # For now, equal weight for all nodes
            locality_score = 0.3

            # Total score (0.0 to 1.0)
            total_score = resource_score + load_score + locality_score

            scored_nodes.append({
                "id": node.id,
                "node_id": node.node_id,
                "region": node.region,
                "cpu_cores": node.cpu_cores,
                "memory_mb": node.memory_mb,
                "cpu_usage": node.cpu_usage_percent,
                "memory_usage": node.memory_usage_percent,
                "score": total_score
            })

        # Sort by score descending
        scored_nodes.sort(key=lambda x: x['score'], reverse=True)

        logger.debug(
            f"Node scoring complete. Top 3: " +
            ", ".join([
                f"{n['node_id']}={n['score']:.2f}"
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
        replicas: List[DeploymentReplica]
    ):
        """
        Transition replicas from PENDING to RUNNING
        Stub for container orchestration

        Args:
            db: Database session
            replicas: List of replicas to transition
        """
        for replica in replicas:
            replica.status = ReplicaStatus.STARTING
            replica.started_at = datetime.now(timezone.utc)

            # TODO: Trigger actual container creation here
            # For now, immediately transition to RUNNING
            replica.status = ReplicaStatus.RUNNING
            replica.container_id = f"stub-container-{replica.id}"

            logger.debug(f"Replica {replica.id} transitioned to RUNNING")

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
                        self.queue.get(), timeout=SCHEDULER_QUEUE_WAIT_TIMEOUT_SECONDS
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
                    storage_gb=deployment_task.get('storage_gb', SCHEDULER_DEFAULT_STORAGE_GB)
                )

                if result['success']:
                    logger.info(f"Deployment {deployment_task['deployment_id']} scheduled successfully")
                else:
                    logger.error(f"Deployment {deployment_task['deployment_id']} scheduling failed: {result.get('error')}")

                self.queue.task_done()

            except Exception as e:
                logger.error(f"Scheduler worker error: {e}", exc_info=True)
                await asyncio.sleep(SCHEDULER_WORKER_ERROR_SLEEP_SECONDS)

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
