"""
Service Orchestration API
Provides endpoints for service management, health checks, and dependency graphs
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


class ServiceRestartRequest(BaseModel):
    """Request to restart a service"""
    force: bool = False


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    services: Dict[str, Any]
    composite_health: str
    unhealthy_services: List[str]
    degraded_services: List[str]


@router.get("/services", summary="List all services")
async def list_services() -> Dict[str, Any]:
    """
    Get list of all services with their current status

    Returns:
        - Service name and status
        - Restart count
        - Last error (if any)
        - Critical flag
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        status_data = enhanced_service_manager.get_status()

        return {
            "success": True,
            "total_services": len(status_data["services"]),
            "services": status_data["services"],
            "is_ready": status_data["is_ready"],
            "initialized": status_data["initialized"]
        }

    except Exception as e:
        logger.error(f"Error listing services: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list services: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckResponse, summary="Overall health status")
async def get_health_status() -> Dict[str, Any]:
    """
    Get comprehensive health status of all services

    Returns:
        - Composite health status
        - Individual service health
        - Unhealthy/degraded services
        - Health check details
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        health_data = enhanced_service_manager.get_health()
        composite_health = enhanced_service_manager.health_manager.get_composite_health()
        unhealthy = enhanced_service_manager.health_manager.get_unhealthy_services()
        degraded = enhanced_service_manager.health_manager.get_degraded_services()

        return {
            "status": "ok",
            "services": health_data,
            "composite_health": composite_health.value,
            "unhealthy_services": unhealthy,
            "degraded_services": degraded
        }

    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get health status: {str(e)}"
        )


@router.post("/restart/{service_name}", summary="Restart a service")
async def restart_service(
    service_name: str,
    request: ServiceRestartRequest = ServiceRestartRequest()
) -> Dict[str, Any]:
    """
    Restart a specific service

    Args:
        service_name: Name of service to restart
        request: Restart options (force flag)

    Returns:
        - Success status
        - New service status
        - Restart count
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        # Check if service exists
        if service_name not in enhanced_service_manager.services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )

        # Get current state
        state = enhanced_service_manager.services[service_name]

        # Check if already at max restarts (unless forced)
        if not request.force and state.restart_count >= enhanced_service_manager.max_restart_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service '{service_name}' has exceeded max restart attempts. Use force=true to override."
            )

        # Perform restart
        await enhanced_service_manager.restart_service(service_name)

        # Get updated state
        state = enhanced_service_manager.services[service_name]

        return {
            "success": True,
            "service": service_name,
            "status": state.status.value,
            "restart_count": state.restart_count,
            "last_restart": state.last_restart.isoformat() if state.last_restart else None,
            "message": f"Service '{service_name}' restarted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting service {service_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart service: {str(e)}"
        )


@router.get("/dependencies", summary="Get service dependency graph")
async def get_dependency_graph() -> Dict[str, Any]:
    """
    Get service dependency graph

    Returns:
        - Startup order
        - Shutdown order
        - Dependency relationships
        - Service layers
        - Graph visualization
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        graph = enhanced_service_manager.dependency_graph

        # Build dependency relationships
        dependencies_map = {}
        for service_name, node in graph.nodes.items():
            dependencies_map[service_name] = {
                "type": node.service_type.value,
                "dependencies": list(node.dependencies),
                "optional_dependencies": list(node.optional_dependencies),
                "dependents": list(node.dependents),
                "layer": graph.get_service_layer(service_name)
            }

        return {
            "success": True,
            "startup_order": graph.get_startup_order(),
            "shutdown_order": graph.get_shutdown_order(),
            "dependencies": dependencies_map,
            "visualization": graph.visualize()
        }

    except Exception as e:
        logger.error(f"Error getting dependency graph: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dependency graph: {str(e)}"
        )


@router.get("/metrics", summary="Get service metrics")
async def get_service_metrics() -> Dict[str, Any]:
    """
    Get comprehensive service metrics

    Returns:
        - Service count by status
        - Restart statistics
        - Health metrics
        - Registry statistics
        - Uptime data
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        status_data = enhanced_service_manager.get_status()
        registry_stats = enhanced_service_manager.registry.get_stats()

        # Calculate metrics
        total_services = len(enhanced_service_manager.services)
        running_services = sum(
            1 for s in enhanced_service_manager.services.values()
            if s.status.value == "running"
        )
        failed_services = sum(
            1 for s in enhanced_service_manager.services.values()
            if s.status.value == "failed"
        )
        total_restarts = sum(
            s.restart_count for s in enhanced_service_manager.services.values()
        )

        # Health metrics
        health_data = enhanced_service_manager.get_health()
        healthy_count = sum(
            1 for h in health_data.values()
            if h.get("status") == "healthy"
        )

        return {
            "success": True,
            "metrics": {
                "total_services": total_services,
                "running_services": running_services,
                "failed_services": failed_services,
                "stopped_services": total_services - running_services - failed_services,
                "total_restarts": total_restarts,
                "healthy_services": healthy_count,
                "unhealthy_services": total_services - healthy_count,
                "is_ready": status_data["is_ready"],
                "initialized": status_data["initialized"]
            },
            "registry_stats": registry_stats,
            "service_details": status_data["services"]
        }

    except Exception as e:
        logger.error(f"Error getting service metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service metrics: {str(e)}"
        )


@router.get("/service/{service_name}", summary="Get service details")
async def get_service_details(service_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific service

    Args:
        service_name: Name of the service

    Returns:
        - Service status
        - Health check history
        - Dependencies
        - Restart history
        - Registry metadata
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        # Check if service exists
        if service_name not in enhanced_service_manager.services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )

        state = enhanced_service_manager.services[service_name]

        # Get health check history
        health_history = []
        if service_name in enhanced_service_manager.health_manager.checkers:
            checker = enhanced_service_manager.health_manager.checkers[service_name]
            health_history = [
                check.to_dict() for check in checker.get_history(limit=20)
            ]

        # Get dependencies
        graph = enhanced_service_manager.dependency_graph
        dependencies = {
            "required": list(graph.get_dependencies(service_name)),
            "optional": list(graph.get_optional_dependencies(service_name)),
            "dependents": list(graph.get_dependents(service_name)),
            "layer": graph.get_service_layer(service_name)
        }

        # Get registry metadata
        registry_meta = enhanced_service_manager.registry.get_service(service_name)
        registry_data = registry_meta.to_dict() if registry_meta else None

        return {
            "success": True,
            "service": service_name,
            "status": state.status.value,
            "restart_count": state.restart_count,
            "last_restart": state.last_restart.isoformat() if state.last_restart else None,
            "last_error": state.last_error,
            "is_critical": state.is_critical,
            "dependencies": dependencies,
            "health_history": health_history,
            "registry_metadata": registry_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service details for {service_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service details: {str(e)}"
        )


@router.post("/health/check-now", summary="Force immediate health check")
async def force_health_check() -> Dict[str, Any]:
    """
    Force an immediate health check on all services

    Returns:
        - Health check results for all services
        - Composite health status
    """
    try:
        from ..services.enhanced_service_manager import enhanced_service_manager

        # Get all service instances
        service_instances = {
            name: state.instance
            for name, state in enhanced_service_manager.services.items()
            if state.instance is not None
        }

        # Perform health checks
        results = await enhanced_service_manager.health_manager.check_all_now(service_instances)

        # Convert to dict
        results_dict = {
            name: result.to_dict()
            for name, result in results.items()
        }

        composite_health = enhanced_service_manager.health_manager.get_composite_health()

        return {
            "success": True,
            "timestamp": results[list(results.keys())[0]].timestamp.isoformat() if results else None,
            "composite_health": composite_health.value,
            "results": results_dict
        }

    except Exception as e:
        logger.error(f"Error forcing health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform health check: {str(e)}"
        )
