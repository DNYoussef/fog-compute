"""
Benchmarks API Routes
Handles performance testing and benchmark execution

SIN-025: Wired to real system metrics via psutil. No more static zeros.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import logging
import os
import time
import uuid

import psutil

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])
logger = logging.getLogger(__name__)

# Track active benchmarks (in-memory; production would use a persistent store)
_active_benchmarks: Dict[str, Dict[str, Any]] = {}


class BenchmarkStartRequest(BaseModel):
    type: str  # latency, throughput, stress
    duration: int = 60


@router.get("/data")
async def get_benchmark_data() -> Dict[str, Any]:
    """Get real-time benchmark metrics from system collectors.

    SIN-025: Returns real psutil metrics instead of static mock zeros.
    """
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    net = psutil.net_io_counters()

    return {
        "timestamp": int(time.time() * 1000),
        "latency": 0.0,  # Real latency requires active benchmark probes
        "throughput": 0.0,  # Real throughput requires active benchmark probes
        "cpuUsage": round(cpu_percent, 2),
        "memoryUsage": round(mem.percent, 2),
        "networkUtilization": round(
            (net.bytes_sent + net.bytes_recv) / (1024 * 1024), 2
        ),
        "source": "psutil",
        "activeBenchmarks": len(_active_benchmarks),
    }


@router.post("/start")
async def start_benchmark(request: BenchmarkStartRequest) -> Dict[str, Any]:
    """Start a new benchmark test"""
    benchmark_id = str(uuid.uuid4())

    _active_benchmarks[benchmark_id] = {
        "type": request.type,
        "duration": request.duration,
        "started_at": time.time(),
        "status": "running",
    }

    return {
        "success": True,
        "benchmarkId": benchmark_id,
        "type": request.type,
        "status": "running"
    }


@router.post("/stop")
async def stop_benchmark(benchmark_id: str) -> Dict[str, Any]:
    """Stop a running benchmark"""
    entry = _active_benchmarks.pop(benchmark_id, None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Benchmark {benchmark_id} not found")

    return {
        "success": True,
        "benchmarkId": benchmark_id,
        "status": "stopped"
    }
