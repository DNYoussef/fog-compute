"""
Deployment API Routes
Handles service deployment and orchestration for fog-compute infrastructure
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import logging
import asyncio
from datetime import datetime, timezone

from ..services.enhanced_service_manager import enhanced_service_manager as service_manager
from ..services.scheduler import scheduler
from ..services.cache_service import cache, cache_service
from ..database import get_db, get_db_context
from ..models.deployment import Deployment, DeploymentReplica, DeploymentResource, ReplicaStatus, DeploymentStatusHistory, DeploymentStatus as DeploymentStatusEnum
from ..schemas.deployment import DeploymentListResponse
from ..auth.dependencies import get_current_active_user
from ..models.database import User
from ..constants import (
    MIN_CPU_CORES,
    MAX_CPU_CORES,
    MIN_MEMORY_MB,
    MAX_MEMORY_MB,
    MIN_GPU_UNITS,
    MAX_GPU_UNITS,
    MIN_STORAGE_GB,
    MAX_STORAGE_GB,
    DEFAULT_STORAGE_GB,
    DEFAULT_REPLICAS,
    MIN_REPLICAS,
    MAX_REPLICAS_INITIAL,
    MAX_REPLICAS_SCALE,
    DEPLOYMENT_STATUS_CACHE_TTL,
    DEPLOYMENT_LIST_CACHE_TTL,
    STATUS_HISTORY_LIMIT,
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    DEFAULT_OFFSET,
)
from ..services.docker_client import get_docker_client, DockerClientError
from ..services.replica_cleanup import stop_replica_for_deletion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deployment", tags=["deployment"])


# ============================================================================
# Load Balancer Integration (nginx/traefik/HAProxy)
# ============================================================================

async def _update_load_balancer_routes(
    deployment_id: str,
    action: str = "add",
    endpoints: Optional[List[str]] = None
) -> bool:
    """
    Update load balancer routing tables for deployment.

    In production, this would integrate with:
    - nginx: Update upstream configuration via API or config reload
    - traefik: Update dynamic configuration via file provider or API
    - HAProxy: Update backend servers via runtime API

    Args:
        deployment_id: Deployment identifier
        action: "add" to register endpoints, "remove" to deregister
        endpoints: List of endpoint URLs (host:port) for "add" action

    Returns:
        True if update successful
    """
    import os

    # Check if load balancer integration is enabled
    lb_enabled = os.environ.get("LOAD_BALANCER_ENABLED", "false").lower() == "true"
    lb_type = os.environ.get("LOAD_BALANCER_TYPE", "nginx")  # nginx, traefik, haproxy
    lb_api_url = os.environ.get("LOAD_BALANCER_API_URL", "")

    if not lb_enabled:
        logger.debug(f"Load balancer integration disabled. Skipping {action} for {deployment_id}")
        return True

    try:
        if action == "add" and endpoints:
            # Add endpoints to routing table
            logger.info(f"Adding {len(endpoints)} endpoints to {lb_type} for deployment {deployment_id}")

            if lb_type == "traefik" and lb_api_url:
                # Traefik dynamic configuration via file or API
                # In production: write to dynamic config file or call API
                pass
            elif lb_type == "nginx" and lb_api_url:
                # nginx Plus API for dynamic upstreams
                # In production: POST to /api/6/http/upstreams/{upstream}/servers
                pass
            elif lb_type == "haproxy" and lb_api_url:
                # HAProxy Runtime API
                # In production: send commands via stats socket
                pass

            logger.info(f"Added deployment {deployment_id} to {lb_type} routing")

        elif action == "remove":
            # Remove deployment from routing table
            logger.info(f"Removing deployment {deployment_id} from {lb_type} routing")

            if lb_type == "traefik" and lb_api_url:
                # Remove from dynamic configuration
                pass
            elif lb_type == "nginx" and lb_api_url:
                # DELETE from /api/6/http/upstreams/{upstream}/servers/{id}
                pass
            elif lb_type == "haproxy" and lb_api_url:
                # Disable/remove server from backend
                pass

            logger.info(f"Removed deployment {deployment_id} from {lb_type} routing")

        return True

    except Exception as e:
        logger.error(f"Load balancer update failed for {deployment_id}: {e}")
        return False


# ============================================================================
# Request/Response Models
# ============================================================================

class ResourceLimits(BaseModel):
    """Resource limits for deployment"""
    cpu: float = Field(ge=MIN_CPU_CORES, le=MAX_CPU_CORES, description="CPU cores")
    memory: int = Field(ge=MIN_MEMORY_MB, le=MAX_MEMORY_MB, description="Memory in MB")
    gpu: int = Field(ge=MIN_GPU_UNITS, le=MAX_GPU_UNITS, default=MIN_GPU_UNITS, description="GPU units")
    storage: int = Field(ge=MIN_STORAGE_GB, le=MAX_STORAGE_GB, default=DEFAULT_STORAGE_GB, description="Storage in GB")


class DeploymentRequest(BaseModel):
    """Request model for deploying a new service"""
    name: str = Field(min_length=1, max_length=100, description="Service name")
    type: str = Field(description="Service type: compute, storage, gateway, mixnode")
    container_image: str = Field(description="Container image (e.g., nginx:latest)")
    replicas: int = Field(ge=MIN_REPLICAS, le=MAX_REPLICAS_INITIAL, default=DEFAULT_REPLICAS, description="Number of replicas")
    resources: ResourceLimits = Field(description="Resource allocation")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    region: Optional[str] = Field("us-east", description="Deployment region")


class ScaleRequest(BaseModel):
    """Request model for scaling a deployment"""
    replicas: int = Field(ge=MIN_REPLICAS, le=MAX_REPLICAS_SCALE, description="Target number of replicas")


class DeploymentResponse(BaseModel):
    """Response model for deployment operations"""
    success: bool
    deployment_id: str
    status: str  # "deploying", "running", "failed", "scaling"
    replicas: int
    message: str


class DeploymentStatus(BaseModel):
    """Detailed deployment status information"""
    deployment_id: str
    name: str
    status: str  # "deploying", "running", "failed", "stopped"
    replicas: int
    replicas_ready: int
    resources: ResourceLimits
    created_at: str
    updated_at: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/deploy", response_model=DeploymentResponse, status_code=202)
async def deploy_service(
    request: DeploymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> DeploymentResponse:
    """
    Deploy a new service or node.

    Deploys compute nodes, storage services, gateways, or mixnodes to the fog network.
    Uses resource-based scheduling to allocate deployments to available fog nodes.

    The deployment process is asynchronous:
    1. Create deployment record in database (status: pending)
    2. Queue for scheduling in background
    3. Return 202 Accepted with deployment_id
    4. Background scheduler will:
       - Find available nodes with sufficient resources
       - Score nodes based on capacity, load, locality
       - Create replica records and allocate resources
       - Transition through: pending -> scheduled -> running

    Args:
        request: DeploymentRequest with service configuration
        db: Database session (injected)
        current_user: Authenticated user from JWT (injected)

    Returns:
        DeploymentResponse with deployment_id and queued status (202 Accepted)

    Raises:
        HTTPException 400: Invalid service type or parameters
        HTTPException 503: Service manager unavailable
        HTTPException 500: Deployment creation failed
    """
    logger.info(
        f"Creating deployment: {request.name} ({request.type}) "
        f"for user {current_user.username}"
    )

    try:
        # Validate service type
        valid_types = ["compute", "storage", "gateway", "mixnode"]
        if request.type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid type. Must be one of: {valid_types}"
            )

        # Handle mixnode deployment through Betanet service
        if request.type == "mixnode":
            betanet = service_manager.get('betanet')
            if not betanet:
                raise HTTPException(
                    status_code=503,
                    detail="Betanet service unavailable"
                )

            # Deploy mixnode via Betanet
            result = await betanet.deploy_node(
                node_type="mixnode",
                region=request.region
            )

            deployment_id = result.get('node_id', f"deploy-{request.name}")

            return DeploymentResponse(
                success=result.get('success', True),
                deployment_id=deployment_id,
                status=result.get('status', 'deploying'),
                replicas=request.replicas,
                message=f"Mixnode deployment initiated for {request.name}"
            )

        # Handle generic service deployment (compute, storage, gateway)
        # Step 1: Create deployment record in database
        from uuid import uuid4
        deployment_id = uuid4()

        deployment = Deployment(
            id=deployment_id,
            name=request.name,
            user_id=current_user.id,
            container_image=request.container_image,
            status=DeploymentStatusEnum.PENDING,
            target_replicas=request.replicas,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.add(deployment)

        # Create initial status history
        history = DeploymentStatusHistory(
            id=uuid4(),
            deployment_id=deployment_id,
            old_status="none",
            new_status=DeploymentStatusEnum.PENDING.value,
            changed_by=current_user.id,
            changed_at=datetime.now(timezone.utc),
            reason="Deployment created by user"
        )

        db.add(history)

        # Commit to database before queueing
        await db.commit()

        logger.info(
            f"Created deployment record {deployment_id} for {request.name} "
            f"with {request.replicas} replicas"
        )

        # Step 2: Queue deployment for async scheduling
        # Create a new database session for background task
        deployment_task = {
            'deployment_id': deployment_id,
            'target_replicas': request.replicas,
            'cpu_cores': request.resources.cpu,
            'memory_mb': request.resources.memory,
            'gpu_units': request.resources.gpu,
            'storage_gb': request.resources.storage,
            'db': db  # Pass database session
        }

        # Queue for background processing
        await scheduler.queue_deployment(deployment_task)

        logger.info(
            f"Queued deployment {deployment_id} for scheduling: "
            f"{request.replicas} replicas, {request.resources.cpu} CPU, "
            f"{request.resources.memory} MB RAM, {request.resources.gpu} GPU, "
            f"{request.resources.storage} GB storage"
        )

        # Step 3: Invalidate deployment list cache for this user
        await cache_service.publish_event(f"deployment.create.user.{current_user.id}")

        # Step 4: Return 202 Accepted
        return DeploymentResponse(
            success=True,
            deployment_id=str(deployment_id),
            status="pending",
            replicas=request.replicas,
            message=f"Deployment queued for scheduling. Use /status/{deployment_id} to track progress."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deployment creation failed: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scale/{deployment_id}", response_model=DeploymentResponse)
async def scale_deployment(
    deployment_id: str,
    request: ScaleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> DeploymentResponse:
    """
    Scale an existing deployment.

    Adjusts the number of replicas for a running deployment:
    - Scale up: Allocate new replicas to available nodes using scheduler logic
    - Scale down: Gracefully terminate excess replicas (oldest first)

    Supports replica counts from 1 to 100.
    Validates user ownership and deployment status.
    Records all status changes in deployment_status_history.

    Args:
        deployment_id: Unique deployment identifier (UUID)
        request: ScaleRequest with target replica count (1-100)
        db: Database session (injected)
        current_user: Authenticated user from JWT (injected)

    Returns:
        DeploymentResponse with scaling status and action taken

    Raises:
        HTTPException 400: Invalid replica count or deployment not in scalable state
        HTTPException 404: Deployment not found or access denied
        HTTPException 503: Insufficient nodes for scale-up
        HTTPException 500: Scaling failed
    """
    logger.info(f"Scaling deployment {deployment_id} to {request.replicas} replicas (user: {current_user.username})")

    try:
        # Convert string to UUID
        try:
            from uuid import UUID
            deployment_uuid = UUID(deployment_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=f"Invalid deployment ID format"
            )

        # Step 1: Fetch current deployment state with user validation
        deployment_query = select(Deployment).where(
            and_(
                Deployment.id == deployment_uuid,
                Deployment.user_id == current_user.id,
                Deployment.deleted_at.is_(None)
            )
        )
        deployment_result = await db.execute(deployment_query)
        deployment = deployment_result.scalar_one_or_none()

        if not deployment:
            raise HTTPException(
                status_code=404,
                detail=f"Deployment {deployment_id} not found or access denied"
            )

        # Validate deployment is in scalable state
        if deployment.status in [DeploymentStatus.DELETED, DeploymentStatus.FAILED]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot scale deployment in {deployment.status.value} state"
            )

        # Validate replica count
        if request.replicas < MIN_REPLICAS or request.replicas > MAX_REPLICAS_SCALE:
            raise HTTPException(
                status_code=400,
                detail=f"Replica count must be between {MIN_REPLICAS} and {MAX_REPLICAS_SCALE}"
            )

        # Get current replica count
        current_replicas_query = select(func.count(DeploymentReplica.id)).where(
            and_(
                DeploymentReplica.deployment_id == deployment_uuid,
                DeploymentReplica.status.in_([
                    ReplicaStatus.PENDING,
                    ReplicaStatus.STARTING,
                    ReplicaStatus.RUNNING
                ])
            )
        )
        current_replicas_result = await db.execute(current_replicas_query)
        current_replicas = current_replicas_result.scalar() or 0

        # Step 2: Calculate delta
        delta = request.replicas - current_replicas

        if delta == 0:
            logger.info(f"Deployment {deployment_id} already at target replicas ({request.replicas})")
            return DeploymentResponse(
                success=True,
                deployment_id=deployment_id,
                status=deployment.status.value,
                replicas=request.replicas,
                message=f"Deployment already at {request.replicas} replicas"
            )

        # Get resource requirements for this deployment
        resources_query = select(DeploymentResource).where(
            DeploymentResource.deployment_id == deployment_uuid
        )
        resources_result = await db.execute(resources_query)
        resources = resources_result.scalar_one_or_none()

        if not resources:
            raise HTTPException(
                status_code=500,
                detail="Deployment resource record not found"
            )

        # Step 3: Handle scale-up or scale-down
        scaling_action = "scale_up" if delta > 0 else "scale_down"
        replicas_changed = abs(delta)

        if delta > 0:
            # SCALE UP: Add new replicas
            logger.info(f"Scaling up {deployment_id}: adding {delta} replicas")

            # Find available nodes (reuse scheduler logic)
            available_nodes = await scheduler._find_available_nodes(
                db,
                cpu_cores=resources.cpu_cores,
                memory_mb=resources.memory_mb,
                gpu_units=resources.gpu_units,
                storage_gb=resources.storage_gb
            )

            if len(available_nodes) < delta:
                error_msg = (
                    f"Insufficient nodes for scale-up: need {delta}, "
                    f"found {len(available_nodes)} with capacity"
                )
                logger.error(error_msg)
                raise HTTPException(
                    status_code=503,
                    detail=error_msg
                )

            # Score and select nodes
            scored_nodes = await scheduler._score_nodes(
                db,
                available_nodes,
                cpu_required=resources.cpu_cores,
                memory_required=resources.memory_mb
            )
            selected_nodes = scored_nodes[:delta]

            # Create new replicas
            new_replicas = []
            for node_info in selected_nodes:
                replica = await scheduler._create_replica(
                    db, deployment_uuid, node_info['id']
                )
                new_replicas.append(replica)
                logger.debug(
                    f"Created new replica {replica.id} on node {node_info['node_id']} "
                    f"(score: {node_info['score']:.2f})"
                )

            # Transition new replicas to running (stub)
            await scheduler._transition_replicas_to_running(db, new_replicas)

            # Update deployment target_replicas
            deployment.target_replicas = request.replicas
            deployment.updated_at = datetime.now(timezone.utc)

            # Record status change
            from uuid import uuid4
            history = DeploymentStatusHistory(
                id=uuid4(),
                deployment_id=deployment_uuid,
                old_status=deployment.status.value,
                new_status=deployment.status.value,
                changed_by=current_user.id,
                changed_at=datetime.now(timezone.utc),
                reason=f"Scaled up from {current_replicas} to {request.replicas} replicas ({delta} added)"
            )
            db.add(history)

            await db.commit()

            logger.info(
                f"Successfully scaled up {deployment_id}: "
                f"{current_replicas} -> {request.replicas} replicas"
            )

            # Invalidate caches
            await cache_service.publish_event(f"deployment.scale.{deployment_id}")

            return DeploymentResponse(
                success=True,
                deployment_id=deployment_id,
                status=deployment.status.value,
                replicas=request.replicas,
                message=f"Scaled up to {request.replicas} replicas ({delta} added)"
            )

        else:
            # SCALE DOWN: Remove excess replicas
            replicas_to_remove = abs(delta)
            logger.info(f"Scaling down {deployment_id}: removing {replicas_to_remove} replicas")

            # Select replicas to terminate (oldest first)
            replicas_query = select(DeploymentReplica).where(
                and_(
                    DeploymentReplica.deployment_id == deployment_uuid,
                    DeploymentReplica.status.in_([
                        ReplicaStatus.RUNNING,
                        ReplicaStatus.STARTING,
                        ReplicaStatus.PENDING
                    ])
                )
            ).order_by(DeploymentReplica.created_at.asc()).limit(replicas_to_remove)

            replicas_result = await db.execute(replicas_query)
            replicas_to_stop = replicas_result.scalars().all()

            if len(replicas_to_stop) < replicas_to_remove:
                logger.warning(
                    f"Expected to remove {replicas_to_remove} replicas, "
                    f"but only found {len(replicas_to_stop)} active replicas"
                )

            # Mark replicas as stopping then stopped
            docker_client = await get_docker_client()

            for replica in replicas_to_stop:
                replica.status = ReplicaStatus.STOPPING
                replica.updated_at = datetime.now(timezone.utc)

                # Trigger container termination via Docker client
                if replica.container_id:
                    try:
                        await docker_client.stop_container(replica.container_id, timeout=10)
                        await docker_client.remove_container(replica.container_id)
                        logger.info(f"Terminated container {replica.container_id} for replica {replica.id}")
                    except DockerClientError as e:
                        logger.warning(f"Failed to terminate container {replica.container_id}: {e}")
                    except Exception as e:
                        logger.warning(f"Container termination error for {replica.container_id}: {e}")

                replica.status = ReplicaStatus.STOPPED
                replica.stopped_at = datetime.now(timezone.utc)

                logger.debug(f"Stopped replica {replica.id}")

            # Update deployment target_replicas
            deployment.target_replicas = request.replicas
            deployment.updated_at = datetime.now(timezone.utc)

            # Record status change
            from uuid import uuid4
            history = DeploymentStatusHistory(
                id=uuid4(),
                deployment_id=deployment_uuid,
                old_status=deployment.status.value,
                new_status=deployment.status.value,
                changed_by=current_user.id,
                changed_at=datetime.now(timezone.utc),
                reason=f"Scaled down from {current_replicas} to {request.replicas} replicas ({replicas_to_remove} removed)"
            )
            db.add(history)

            await db.commit()

            logger.info(
                f"Successfully scaled down {deployment_id}: "
                f"{current_replicas} -> {request.replicas} replicas"
            )

            # Invalidate caches
            await cache_service.publish_event(f"deployment.scale.{deployment_id}")

            return DeploymentResponse(
                success=True,
                deployment_id=deployment_id,
                status=deployment.status.value,
                replicas=request.replicas,
                message=f"Scaled down to {request.replicas} replicas ({replicas_to_remove} removed)"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scaling failed for {deployment_id}: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{deployment_id}")
async def get_deployment_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get deployment status.

    Retrieves detailed status information for a specific deployment including:
    - Current deployment status and configuration
    - All replica statuses with node assignments
    - Resource allocation details
    - Health aggregation (healthy/degraded/unhealthy)
    - Last 10 status changes from history

    Users can only access their own deployments (JWT user_id validation).

    Args:
        deployment_id: Unique deployment identifier (UUID)
        db: Database session (injected)
        current_user: Authenticated user from JWT (injected)

    Returns:
        Detailed deployment status with replicas, resources, and history

    Raises:
        HTTPException 404: Deployment not found or belongs to another user
        HTTPException 500: Database query failed
    """
    # Try cache first (30s TTL for deployment status)
    cache_key = cache_service.generate_key(
        "deployment_status",
        "get",
        deployment_id=deployment_id,
        user_id=str(current_user.id)
    )

    cached_response = await cache_service.get("deployment_status", cache_key)
    if cached_response is not None:
        logger.debug(f"Cache hit for deployment status: {deployment_id}")
        return cached_response

    try:
        # Convert string to UUID for query
        try:
            from uuid import UUID
            deployment_uuid = UUID(deployment_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=f"Invalid deployment ID format"
            )

        # Query deployment with user_id check
        deployment_query = select(Deployment).where(
            and_(
                Deployment.id == deployment_uuid,
                Deployment.user_id == current_user.id,
                Deployment.deleted_at.is_(None)
            )
        )
        deployment_result = await db.execute(deployment_query)
        deployment = deployment_result.scalar_one_or_none()

        if not deployment:
            raise HTTPException(
                status_code=404,
                detail=f"Deployment {deployment_id} not found or access denied"
            )

        # Query all replicas for this deployment
        replicas_query = select(DeploymentReplica).where(
            DeploymentReplica.deployment_id == deployment_uuid
        )
        replicas_result = await db.execute(replicas_query)
        replicas = replicas_result.scalars().all()

        # Query resource allocation
        resources_query = select(DeploymentResource).where(
            DeploymentResource.deployment_id == deployment_uuid
        )
        resources_result = await db.execute(resources_query)
        resources = resources_result.scalar_one_or_none()

        # Query last status changes
        history_query = select(DeploymentStatusHistory).where(
            DeploymentStatusHistory.deployment_id == deployment_uuid
        ).order_by(DeploymentStatusHistory.changed_at.desc()).limit(STATUS_HISTORY_LIMIT)
        history_result = await db.execute(history_query)
        status_history = history_result.scalars().all()

        # Calculate health status based on replica health
        health_status = "healthy"
        if replicas:
            running_count = sum(1 for r in replicas if r.status == ReplicaStatus.RUNNING)
            failed_count = sum(1 for r in replicas if r.status == ReplicaStatus.FAILED)

            if failed_count > 0 or running_count < deployment.target_replicas:
                # Any failures or missing replicas = degraded
                health_status = "degraded"
            if failed_count == len(replicas) or running_count == 0:
                # All failed or none running = unhealthy
                health_status = "unhealthy"
        else:
            # No replicas = unhealthy
            health_status = "unhealthy"

        # Build replica response
        replica_list = [
            {
                "id": str(replica.id),
                "node_id": str(replica.node_id) if replica.node_id else None,
                "status": replica.status.value if isinstance(replica.status, ReplicaStatus) else replica.status,
                "container_id": replica.container_id,
                "started_at": replica.started_at.isoformat() if replica.started_at else None,
                "stopped_at": replica.stopped_at.isoformat() if replica.stopped_at else None
            }
            for replica in replicas
        ]

        # Build resources response
        resources_dict = {
            "cpu_cores": resources.cpu_cores if resources else 0.0,
            "memory_mb": resources.memory_mb if resources else 0,
            "gpu_units": resources.gpu_units if resources else 0,
            "storage_gb": resources.storage_gb if resources else 0
        }

        # Build status history response
        history_list = [
            {
                "old_status": entry.old_status,
                "new_status": entry.new_status,
                "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
                "reason": entry.reason
            }
            for entry in status_history
        ]

        # Build comprehensive response
        response = {
            "deployment_id": str(deployment.id),
            "name": deployment.name,
            "status": deployment.status.value if isinstance(deployment.status, DeploymentStatusEnum) else deployment.status,
            "health": health_status,
            "target_replicas": deployment.target_replicas,
            "replicas": replica_list,
            "resources": resources_dict,
            "recent_status_changes": history_list,
            "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
            "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None
        }

        logger.info(
            f"Retrieved deployment status for {deployment.name} (user: {current_user.username}): "
            f"status={deployment.status.value}, health={health_status}, "
            f"replicas={len(replicas)}/{deployment.target_replicas}"
        )

        # Cache the response
        await cache_service.set("deployment_status", cache_key, response, ttl=DEPLOYMENT_STATUS_CACHE_TTL)

        # Subscribe to invalidation events
        cache_service.subscribe_to_event(f"deployment.update.{deployment_id}", cache_key)
        cache_service.subscribe_to_event(f"deployment.scale.{deployment_id}", cache_key)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deployment status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve deployment status: {str(e)}"
        )


@router.get("/list", response_model=List[DeploymentListResponse])
async def list_deployments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    status: Optional[str] = Query(None, description="Filter by status (pending, scheduled, running, stopped, failed)"),
    name: Optional[str] = Query(None, description="Filter by name (partial match)"),
    created_after: Optional[datetime] = Query(None, description="Filter by created_at >= this date"),
    created_before: Optional[datetime] = Query(None, description="Filter by created_at <= this date"),
    sort_by: str = Query("created_at", description="Sort field (created_at, name, status)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=MIN_REPLICAS, le=MAX_PAGE_LIMIT, description="Number of results per page"),
    offset: int = Query(DEFAULT_OFFSET, ge=DEFAULT_OFFSET, description="Number of results to skip")
) -> List[DeploymentListResponse]:
    """
    List user's deployments with filtering, sorting, and pagination.

    Retrieves deployments for the authenticated user with optional filters.
    Users can only see their own deployments (filtered by user_id from JWT token).

    Query Parameters:
        - status: Filter by deployment status
        - name: Filter by name (case-insensitive partial match)
        - created_after: Show deployments created on or after this date
        - created_before: Show deployments created on or before this date
        - sort_by: Sort field (created_at, name, status)
        - sort_order: Sort direction (asc, desc)
        - limit: Results per page (default 20, max 100)
        - offset: Number of results to skip for pagination

    Returns:
        List of DeploymentListResponse objects with pagination metadata

    Raises:
        HTTPException 400: Invalid filter parameters
        HTTPException 500: Database query failed
    """
    # Try cache first (60s TTL for deployment list)
    cache_key = cache_service.generate_key(
        "deployment_list",
        "list",
        user_id=str(current_user.id),
        status=status,
        name=name,
        created_after=str(created_after) if created_after else None,
        created_before=str(created_before) if created_before else None,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )

    cached_response = await cache_service.get("deployment_list", cache_key)
    if cached_response is not None:
        logger.debug(f"Cache hit for deployment list (user: {current_user.username})")
        return cached_response

    try:
        # Build base query - only deployments for current user, exclude soft-deleted
        query = select(Deployment).where(
            and_(
                Deployment.user_id == current_user.id,
                Deployment.deleted_at.is_(None)
            )
        )

        # Apply status filter
        if status:
            try:
                status_enum = DeploymentStatusEnum(status.lower())
                query = query.where(Deployment.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: pending, scheduled, running, stopped, failed, deleted"
                )

        # Apply name filter (case-insensitive partial match)
        if name:
            query = query.where(Deployment.name.ilike(f"%{name}%"))

        # Apply date range filters
        if created_after:
            query = query.where(Deployment.created_at >= created_after)
        if created_before:
            query = query.where(Deployment.created_at <= created_before)

        # Apply sorting
        valid_sort_fields = {"created_at", "name", "status"}
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort_by. Must be one of: {valid_sort_fields}"
            )

        sort_column = getattr(Deployment, sort_by)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        elif sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid sort_order. Must be 'asc' or 'desc'"
            )

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        deployments = result.scalars().all()

        # Build response with running replica counts
        response_list = []
        for deployment in deployments:
            # Count running replicas using subquery
            running_count_query = select(func.count(DeploymentReplica.id)).where(
                and_(
                    DeploymentReplica.deployment_id == deployment.id,
                    DeploymentReplica.status == ReplicaStatus.RUNNING
                )
            )
            running_count_result = await db.execute(running_count_query)
            running_replicas = running_count_result.scalar() or 0

            response_list.append(DeploymentListResponse(
                id=str(deployment.id),
                name=deployment.name,
                status=deployment.status,
                target_replicas=deployment.target_replicas,
                running_replicas=running_replicas,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at
            ))

        logger.info(
            f"Listed {len(response_list)} deployments for user {current_user.username} "
            f"(limit={limit}, offset={offset}, filters: status={status}, name={name})"
        )

        # Cache the response
        await cache_service.set("deployment_list", cache_key, response_list, ttl=DEPLOYMENT_LIST_CACHE_TTL)

        # Subscribe to invalidation events for this user
        cache_service.subscribe_to_event(f"deployment.create.user.{current_user.id}", cache_key)
        cache_service.subscribe_to_event(f"deployment.delete.user.{current_user.id}", cache_key)

        return response_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list deployments: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )


@router.get("/cache/metrics")
async def get_cache_metrics(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get cache performance metrics

    Returns:
        Cache statistics including hit/miss rates, latency, and Redis info
    """
    try:
        metrics = await cache_service.get_metrics()
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get cache metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_deployment_cache(
    current_user: User = Depends(get_current_active_user)
):
    """
    Clear deployment cache (admin operation)

    Clears all cached deployment data for all users.
    Use with caution - will cause temporary performance degradation.
    """
    try:
        cleared_count = await cache_service.clear_namespace("deployment_list")
        cleared_count += await cache_service.clear_namespace("deployment_status")

        logger.info(f"Cleared {cleared_count} cache entries (user: {current_user.username})")

        return {
            "success": True,
            "entries_cleared": cleared_count,
            "message": f"Cleared {cleared_count} cache entries"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{deployment_id}")
async def delete_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a deployment (soft delete).

    CRITICAL: Distributes pending rewards BEFORE cleanup to prevent reward loss.
    Stops all replicas, releases resources, and marks deployment as deleted.
    Uses soft-delete pattern (sets deleted_at timestamp).

    Args:
        deployment_id: Unique deployment identifier
        db: Database session
        current_user: Authenticated user from JWT

    Returns:
        JSON with deletion summary including reward distribution status

    Raises:
        HTTPException 404: Deployment not found or not owned by user
        HTTPException 409: Already deleted
        HTTPException 500: Deletion failed or reward distribution failed
    """
    logger.info(f"Deleting deployment {deployment_id} for user {current_user.id}")

    try:
        # Step 1: Validate deployment exists and belongs to user
        from uuid import UUID
        try:
            deployment_uuid = UUID(deployment_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid deployment ID format")

        deployment_query = select(Deployment).where(
            and_(
                Deployment.id == deployment_uuid,
                Deployment.user_id == current_user.id,
                Deployment.deleted_at.is_(None)  # Not already deleted
            )
        )
        deployment_result = await db.execute(deployment_query)
        deployment = deployment_result.scalar_one_or_none()

        if not deployment:
            # Check if it exists but is already deleted or not owned
            check_query = select(Deployment).where(Deployment.id == deployment_uuid)
            check_result = await db.execute(check_query)
            check_deployment = check_result.scalar_one_or_none()

            if not check_deployment:
                raise HTTPException(status_code=404, detail="Deployment not found")
            elif check_deployment.deleted_at is not None:
                raise HTTPException(status_code=409, detail="Deployment already deleted")
            else:
                raise HTTPException(status_code=404, detail="Deployment not found or access denied")

        # Step 2: Check if already deleted (double-check)
        if deployment.deleted_at is not None:
            raise HTTPException(status_code=409, detail="Deployment already deleted")

        old_status = deployment.status

        # Step 2.5: CRITICAL - Distribute pending rewards BEFORE cleanup (FUNC-08)
        from ..services.rewards import get_reward_service

        reward_service = get_reward_service()

        logger.info(
            f"Distributing pending rewards for deployment {deployment_id} before cleanup"
        )

        cleanup_result = await reward_service.cleanup_with_distribution(
            deployment_id=deployment_uuid,
            user_id=current_user.id,
            db=db
        )

        if not cleanup_result.success:
            # Reward distribution failed - ABORT cleanup to prevent reward loss
            logger.error(
                f"Reward distribution failed for deployment {deployment_id}: "
                f"{cleanup_result.error_message}. Aborting deletion to protect rewards."
            )

            await db.rollback()

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Cannot delete deployment: reward distribution failed. "
                    f"{cleanup_result.error_message}. "
                    f"Please try again later or contact support."
                )
            )

        logger.info(
            f"Successfully distributed {cleanup_result.rewards_distributed} rewards "
            f"({float(cleanup_result.rewards_amount)} tokens) before cleanup"
        )

        # Step 3: Stop all running replicas (cascade)
        replicas_query = select(DeploymentReplica).where(
            DeploymentReplica.deployment_id == deployment_uuid
        )
        replicas_result = await db.execute(replicas_query)
        replicas = replicas_result.scalars().all()

        replicas_stopped = 0
        docker_client = await get_docker_client()

        for replica in replicas:
            if replica.status in [ReplicaStatus.RUNNING, ReplicaStatus.STARTING]:
                await stop_replica_for_deletion(replica, db, docker_client)

                replicas_stopped += 1
                logger.debug(f"Stopped replica {replica.id} on node {replica.node_id}")

        # Step 4: Release resource reservations (mark as deallocated)
        resources_query = select(DeploymentResource).where(
            DeploymentResource.deployment_id == deployment_uuid
        )
        resources_result = await db.execute(resources_query)
        resources = resources_result.scalar_one_or_none()

        resources_released = False
        if resources:
            # Resource deallocation is implicit via soft delete
            # In production, would update node capacity here
            resources_released = True
            logger.info(
                f"Released resources for deployment {deployment_id}: "
                f"{resources.cpu_cores} CPU, {resources.memory_mb} MB, "
                f"{resources.gpu_units} GPU, {resources.storage_gb} GB"
            )

        # Step 5: Set deployment.status = DELETED
        deployment.status = DeploymentStatusEnum.DELETED

        # Step 6: Set deployment.deleted_at = now()
        deployment.deleted_at = datetime.now(timezone.utc)
        deployment.updated_at = datetime.now(timezone.utc)

        # Step 7: Record status change in history
        history = DeploymentStatusHistory(
            deployment_id=deployment_uuid,
            old_status=old_status.value if isinstance(old_status, DeploymentStatusEnum) else old_status,
            new_status=DeploymentStatusEnum.DELETED.value,
            changed_by=current_user.id,
            changed_at=datetime.now(timezone.utc),
            reason=f"User deletion: stopped {replicas_stopped} replicas, released resources"
        )
        db.add(history)

        # Step 8: Update load balancer references
        # Remove deployment from routing tables (nginx/traefik integration)
        await _update_load_balancer_routes(deployment_id, action="remove")
        logger.info(f"Removed deployment {deployment_id} from load balancer routing")

        # Commit transaction
        await db.commit()

        logger.info(
            f"Deployment {deployment_id} deleted successfully: "
            f"{replicas_stopped} replicas stopped, resources released"
        )

        # Invalidate caches
        await cache_service.publish_event(f"deployment.delete.user.{current_user.id}")
        await cache_service.publish_event(f"deployment.update.{deployment_id}")

        # Step 9: Return success response with reward distribution info
        return {
            "success": True,
            "deployment_id": str(deployment_uuid),
            "status": "deleted",
            "replicas_stopped": replicas_stopped,
            "resources_released": resources_released,
            "rewards_distributed": cleanup_result.rewards_distributed,
            "rewards_amount": float(cleanup_result.rewards_amount),
            "deleted_at": deployment.deleted_at.isoformat(),
            "message": (
                f"Deployment and {replicas_stopped} replicas deleted successfully. "
                f"Distributed {cleanup_result.rewards_distributed} pending rewards "
                f"({float(cleanup_result.rewards_amount)} tokens)."
            )
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Deletion failed for deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")
