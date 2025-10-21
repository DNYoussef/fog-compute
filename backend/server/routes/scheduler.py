"""
Batch Scheduler API Routes
Handles job submission, scheduling, and NSGA-II optimization
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.service_manager import service_manager
from ..database import get_db
from ..models.database import Job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class JobSubmitRequest(BaseModel):
    name: str
    sla_tier: str  # platinum, gold, silver, bronze
    cpu_required: float
    memory_required: float
    gpu_required: float = 0.0
    duration_estimate: Optional[float] = None
    data_size_mb: Optional[float] = None


class JobUpdateRequest(BaseModel):
    status: str


@router.get("/stats")
async def get_scheduler_stats() -> Dict[str, Any]:
    """
    Get batch scheduler statistics

    Returns:
        - Job queue metrics
        - SLA compliance rates
        - Resource utilization
        - Optimization metrics
    """
    scheduler = service_manager.get('scheduler')

    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler service unavailable")

    try:
        # Get metrics from NSGA-II scheduler
        metrics = scheduler.get_metrics() if hasattr(scheduler, 'get_metrics') else {}
        job_queue = scheduler.get_job_queue() if hasattr(scheduler, 'get_job_queue') else []

        # Calculate stats
        total_jobs = len(job_queue)
        running_jobs = len([j for j in job_queue if getattr(j, 'status', None) == 'running'])
        pending_jobs = len([j for j in job_queue if getattr(j, 'status', None) == 'pending'])
        completed_jobs = len([j for j in job_queue if getattr(j, 'status', None) == 'completed'])

        return {
            "totalJobs": total_jobs,
            "runningJobs": running_jobs,
            "pendingJobs": pending_jobs,
            "completedJobs": completed_jobs,
            "queueLength": pending_jobs,
            "avgWaitTime": metrics.get('avg_wait_time', 0),
            "slaCompliance": {
                "platinum": metrics.get('sla_platinum', 100),
                "gold": metrics.get('sla_gold', 95),
                "silver": metrics.get('sla_silver', 90),
                "bronze": metrics.get('sla_bronze', 85)
            },
            "resourceUtilization": {
                "cpu": metrics.get('cpu_utilization', 0),
                "memory": metrics.get('memory_utilization', 0),
                "gpu": metrics.get('gpu_utilization', 0)
            },
            "optimizationScore": metrics.get('optimization_score', 0)
        }
    except Exception as e:
        logger.error(f"Error fetching scheduler stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def get_jobs(status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """
    Get job queue

    Args:
        status: Filter by status (pending, running, completed, failed)
        limit: Maximum number of jobs to return

    Returns:
        List of jobs with details
    """
    scheduler = service_manager.get('scheduler')

    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler service unavailable")

    try:
        job_queue = scheduler.get_job_queue() if hasattr(scheduler, 'get_job_queue') else []

        # Filter by status if provided
        if status:
            job_queue = [j for j in job_queue if getattr(j, 'status', None) == status]

        # Limit results
        job_queue = job_queue[:limit]

        # Format jobs
        jobs = []
        for job in job_queue:
            jobs.append({
                "id": getattr(job, 'job_id', str(uuid.uuid4())),
                "name": getattr(job, 'name', 'Unknown'),
                "status": getattr(job, 'status', 'pending'),
                "sla": getattr(job, 'sla_tier', 'bronze'),
                "cpu": getattr(job, 'cpu_required', 0),
                "memory": getattr(job, 'memory_required', 0),
                "gpu": getattr(job, 'gpu_required', 0),
                "node": getattr(job, 'assigned_node', None),
                "submitted": getattr(job, 'submitted_at', datetime.now()).isoformat() if hasattr(job, 'submitted_at') else None,
                "started": getattr(job, 'started_at', None),
                "completed": getattr(job, 'completed_at', None),
                "progress": getattr(job, 'progress', 0)
            })

        return {
            "jobs": jobs,
            "total": len(jobs),
            "filtered": status is not None
        }
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs")
async def submit_job(request: JobSubmitRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Submit a new batch job

    Args:
        Job configuration with resource requirements
        db: Database session (injected)

    Returns:
        Job ID and estimated start time
    """
    try:
        # Create database job record
        db_job = Job(
            name=request.name,
            sla_tier=request.sla_tier,
            cpu_required=request.cpu_required,
            memory_required=request.memory_required,
            gpu_required=request.gpu_required,
            duration_estimate=request.duration_estimate,
            data_size_mb=request.data_size_mb,
            status='pending',
            submitted_at=datetime.utcnow()
        )

        db.add(db_job)
        await db.commit()
        await db.refresh(db_job)

        # Also submit to in-memory scheduler if available
        scheduler = service_manager.get('scheduler')
        if scheduler and hasattr(scheduler, 'submit_job'):
            scheduler.submit_job({
                'job_id': str(db_job.id),
                'name': request.name,
                'sla_tier': request.sla_tier,
                'cpu_required': request.cpu_required,
                'memory_required': request.memory_required,
                'gpu_required': request.gpu_required
            })

        logger.info(f"Job {db_job.id} submitted successfully")

        return {
            "success": True,
            "jobId": str(db_job.id),
            "status": "pending",
            "estimatedStartTime": None,  # Would be calculated by scheduler
            "sla": request.sla_tier
        }
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    """Get details for a specific job"""
    scheduler = service_manager.get('scheduler')

    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler service unavailable")

    try:
        # Find job
        job_queue = scheduler.get_job_queue() if hasattr(scheduler, 'get_job_queue') else []
        job = next((j for j in job_queue if getattr(j, 'job_id', None) == job_id), None)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return {
            "id": job_id,
            "name": getattr(job, 'name', 'Unknown'),
            "status": getattr(job, 'status', 'pending'),
            "sla": getattr(job, 'sla_tier', 'bronze'),
            "cpu": getattr(job, 'cpu_required', 0),
            "memory": getattr(job, 'memory_required', 0),
            "gpu": getattr(job, 'gpu_required', 0),
            "node": getattr(job, 'assigned_node', None),
            "progress": getattr(job, 'progress', 0),
            "submitted": getattr(job, 'submitted_at', None),
            "started": getattr(job, 'started_at', None),
            "completed": getattr(job, 'completed_at', None),
            "logs": getattr(job, 'logs', [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/jobs/{job_id}")
async def update_job(job_id: str, request: JobUpdateRequest) -> Dict[str, Any]:
    """Update job status (cancel, pause, resume)"""
    scheduler = service_manager.get('scheduler')

    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler service unavailable")

    try:
        # Update job status
        if hasattr(scheduler, 'update_job_status'):
            scheduler.update_job_status(job_id, request.status)

        return {
            "success": True,
            "jobId": job_id,
            "status": request.status
        }
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, Any]:
    """Cancel a pending or running job"""
    scheduler = service_manager.get('scheduler')

    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler service unavailable")

    try:
        if hasattr(scheduler, 'cancel_job'):
            scheduler.cancel_job(job_id)

        return {
            "success": True,
            "jobId": job_id,
            "status": "cancelled"
        }
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes")
async def get_nodes() -> Dict[str, Any]:
    """Get available compute nodes for scheduling"""
    scheduler = service_manager.get('scheduler')

    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler service unavailable")

    try:
        nodes = scheduler.nodes if hasattr(scheduler, 'nodes') else []

        return {
            "nodes": [
                {
                    "id": getattr(node, 'node_id', str(i)),
                    "status": getattr(node, 'status', 'active'),
                    "cpu": getattr(node, 'cpu_cores', 0),
                    "memory": getattr(node, 'memory_gb', 0),
                    "gpu": getattr(node, 'gpu_count', 0),
                    "load": getattr(node, 'current_load', 0),
                    "trust": getattr(node, 'trust_score', 1.0)
                }
                for i, node in enumerate(nodes)
            ],
            "total": len(nodes)
        }
    except Exception as e:
        logger.error(f"Error fetching nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
