"""
Shared utilities for fog compute benchmarking infrastructure.
Common logging, metrics collection, and helper functions.
"""

import logging
import time
import psutil
import gc
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import sys


@dataclass
class SystemMetrics:
    """System resource usage metrics"""
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read: int
    disk_io_write: int
    network_io_sent: int
    network_io_recv: int
    open_files: int
    threads: int
    timestamp: float


def setup_logging(output_dir: Path, name: str, verbose: bool = False) -> logging.Logger:
    """Configure logging for fog compute components"""
    log_level = logging.DEBUG if verbose else logging.INFO

    output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(output_dir / f'{name}.log'),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(name)


async def collect_system_metrics() -> SystemMetrics:
    """Collect current system resource metrics"""
    process = psutil.Process()

    # Get I/O counters if available
    try:
        io_counters = process.io_counters()
        disk_read = io_counters.read_bytes
        disk_write = io_counters.write_bytes
    except (AttributeError, psutil.AccessDenied):
        disk_read = disk_write = 0

    # Get network I/O
    try:
        net_io = psutil.net_io_counters()
        net_sent = net_io.bytes_sent if net_io else 0
        net_recv = net_io.bytes_recv if net_io else 0
    except (AttributeError, psutil.AccessDenied):
        net_sent = net_recv = 0

    return SystemMetrics(
        cpu_percent=process.cpu_percent(),
        memory_mb=process.memory_info().rss / 1024 / 1024,
        memory_percent=process.memory_percent(),
        disk_io_read=disk_read,
        disk_io_write=disk_write,
        network_io_sent=net_sent,
        network_io_recv=net_recv,
        open_files=process.num_fds() if hasattr(process, 'num_fds') else 0,
        threads=process.num_threads(),
        timestamp=time.time()
    )


def establish_baseline_metrics() -> Dict[str, Any]:
    """Establish baseline performance metrics"""
    gc.collect()
    process = psutil.Process()

    return {
        'memory': {
            'rss_mb': process.memory_info().rss / 1024 / 1024,
            'vms_mb': process.memory_info().vms / 1024 / 1024,
            'percent': process.memory_percent()
        },
        'timestamp': time.time()
    }


def calculate_improvement(before: float, after: float) -> float:
    """Calculate percentage improvement between before/after values"""
    if before == 0:
        return 0.0
    return ((before - after) / before) * 100


def calculate_grade(pass_rate: float) -> str:
    """Calculate letter grade from pass rate percentage"""
    if pass_rate >= 90:
        return "A"
    elif pass_rate >= 80:
        return "B"
    elif pass_rate >= 70:
        return "C"
    elif pass_rate >= 60:
        return "D"
    else:
        return "F"