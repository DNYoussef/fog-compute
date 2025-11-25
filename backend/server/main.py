"""
Fog Compute Backend API Server
Main FastAPI application that orchestrates all services
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import configuration and services
from .config import settings
from .services.enhanced_service_manager import enhanced_service_manager
from .database import init_db, close_db

# Import all route modules
from .routes import (
    dashboard,
    betanet,
    tokenomics,
    scheduler,
    idle_compute,
    privacy,
    p2p,
    benchmarks,
    auth,
    bitchat,
    orchestration,
    websocket as websocket_routes,
    deployment
)

# Import WebSocket handlers
from .websocket.metrics_stream import MetricsStreamer
from .websocket.server import connection_manager
from .websocket.publishers import publisher_manager
from .services.metrics_aggregator import metrics_aggregator

# Import middleware
from .middleware import RateLimitMiddleware, CSRFMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Fog Compute Backend API Server...")
    logger.info(f"📍 API URL: http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"🔗 CORS Origins: {settings.CORS_ORIGINS}")

    # Diagnostic logging for CI environment
    import os
    import re
    if os.getenv('CI') == 'true':
        logger.info("🔍 CI Environment Detected")
        db_url = settings.DATABASE_URL
        # Censor password: postgresql://user:PASSWORD@host/db → postgresql://user:***@host/db
        censored_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', db_url)
        logger.info(f"🔍 DATABASE_URL: {censored_url}")
        logger.info(f"🔍 Database driver: {'asyncpg' if 'asyncpg' in db_url else 'UNKNOWN (should be asyncpg!)'}")

    # Initialize database
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.warning("⚠️  Database may be unavailable")

    # Initialize all services with enhanced orchestration
    try:
        await enhanced_service_manager.initialize()
        logger.info("✅ All services initialized successfully with enhanced orchestration")
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}")
        logger.warning("⚠️  Some services may be unavailable")

    # Initialize WebSocket infrastructure
    try:
        await connection_manager.start()
        await publisher_manager.start_all()

        # Set up metrics aggregator with alert callback
        metrics_aggregator.set_alert_callback(publisher_manager.publish_alert)

        logger.info("✅ WebSocket infrastructure started successfully")
    except Exception as e:
        logger.error(f"❌ WebSocket initialization failed: {e}")
        logger.warning("⚠️  Real-time updates may be unavailable")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Fog Compute Backend API Server...")

    # Stop WebSocket infrastructure
    try:
        await publisher_manager.stop_all()
        await connection_manager.stop()
        logger.info("✅ WebSocket infrastructure stopped")
    except Exception as e:
        logger.error(f"Error stopping WebSocket infrastructure: {e}")

    await enhanced_service_manager.shutdown()
    await close_db()
    logger.info("✅ Graceful shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Unified backend API for Fog Compute distributed platform",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF protection middleware (after CORS, before rate limiting)
app.add_middleware(
    CSRFMiddleware,
    cookie_secure=settings.API_HOST != "localhost",  # Use secure cookies in production
    cookie_httponly=True,
    cookie_samesite="strict"
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)


# Health check endpoint
@app.get("/health")
async def health_check():
    """System health check"""
    service_health = enhanced_service_manager.get_health()
    is_ready = enhanced_service_manager.is_ready()
    composite_health = enhanced_service_manager.health_manager.get_composite_health()

    return {
        "status": "healthy" if is_ready else "degraded",
        "composite_health": composite_health.value,
        "services": service_health,
        "version": settings.API_VERSION
    }


# Include all route modules
app.include_router(auth.router)  # Auth must be first for proper routing
app.include_router(dashboard.router)
app.include_router(betanet.router)
app.include_router(tokenomics.router)
app.include_router(scheduler.router)
app.include_router(idle_compute.router)
app.include_router(privacy.router)
app.include_router(p2p.router)
app.include_router(benchmarks.router)
app.include_router(bitchat.router)  # BitChat messaging
app.include_router(orchestration.router)  # Service orchestration
app.include_router(websocket_routes.router)  # WebSocket management
app.include_router(deployment.router)  # Deployment orchestration


# WebSocket for real-time metrics
metrics_streamer = MetricsStreamer(enhanced_service_manager)


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    WebSocket endpoint for real-time metrics streaming

    Streams updates every second with:
    - Betanet network status
    - P2P connections
    - Job queue
    - Idle compute devices
    - Token metrics
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: {websocket.client}")

    try:
        await metrics_streamer.stream_metrics(websocket)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


# Root endpoint
@app.get("/")
async def root():
    """API root with service information"""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "operational",
        "endpoints": {
            "auth": "/api/auth/login",
            "register": "/api/auth/register",
            "health": "/health",
            "dashboard": "/api/dashboard/stats",
            "betanet": "/api/betanet/status",
            "tokenomics": "/api/tokenomics/stats",
            "scheduler": "/api/scheduler/stats",
            "idle_compute": "/api/idle-compute/stats",
            "privacy": "/api/privacy/stats",
            "p2p": "/api/p2p/stats",
            "bitchat": "/api/bitchat/stats",
            "orchestration": "/api/orchestration/services",
            "orchestration_health": "/api/orchestration/health",
            "orchestration_dependencies": "/api/orchestration/dependencies",
            "deployment": "/api/deployment/deploy",
            "deployment_list": "/api/deployment/list",
            "deployment_status": "/api/deployment/status/{deployment_id}",
            "websocket": "ws://localhost:8000/ws/metrics",
            "bitchat_ws": "ws://localhost:8000/api/bitchat/ws/{peer_id}"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


def main():
    """Run the API server"""
    logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")

    uvicorn.run(
        "backend.server.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # Enable auto-reload in development
        log_level="info"
    )


if __name__ == "__main__":
    main()
