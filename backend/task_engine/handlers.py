"""
Task Handlers
FOGBURST-004: Pluggable task type handlers

Provides extensible system for different task types.
"""
import asyncio
import logging
import time
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Optional

from .runner import TaskSpec, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class TaskHandler(ABC):
    """
    Abstract base class for task handlers.

    FOGBURST-004: Extensible task handling system.
    """

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Return the task type this handler handles."""
        pass

    @abstractmethod
    async def execute(self, spec: TaskSpec) -> TaskResult:
        """
        Execute the task.

        Args:
            spec: Task specification

        Returns:
            Task result
        """
        pass

    def can_handle(self, spec: TaskSpec) -> bool:
        """Check if this handler can handle the task."""
        return spec.task_type == self.task_type


class ComputeHandler(TaskHandler):
    """
    Handler for compute tasks.

    FOGBURST-004: CPU-bound computation tasks.
    """

    @property
    def task_type(self) -> str:
        return "compute"

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute compute task."""
        start_time = datetime.now(UTC)
        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        payload = spec.payload
        operation = payload.get("operation", "add")

        try:
            if operation == "add":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                computed = a + b
                result.result_data = {"result": computed, "operation": "add"}

            elif operation == "subtract":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                computed = a - b
                result.result_data = {"result": computed, "operation": "subtract"}

            elif operation == "multiply":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                computed = a * b
                result.result_data = {"result": computed, "operation": "multiply"}

            elif operation == "divide":
                a = payload.get("a", 0)
                b = payload.get("b", 1)
                if b == 0:
                    raise ValueError("Division by zero")
                computed = a / b
                result.result_data = {"result": computed, "operation": "divide"}

            elif operation == "power":
                base = payload.get("base", 2)
                exp = payload.get("exp", 10)
                computed = base ** exp
                result.result_data = {"result": computed, "operation": "power"}

            elif operation == "factorial":
                n = payload.get("n", 1)
                computed = 1
                for i in range(2, n + 1):
                    computed *= i
                result.result_data = {"result": computed, "operation": "factorial", "n": n}

            elif operation == "fibonacci":
                n = payload.get("n", 10)
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b
                result.result_data = {"result": a, "operation": "fibonacci", "n": n}

            elif operation == "prime_check":
                n = payload.get("n", 2)
                is_prime = n > 1 and all(n % i != 0 for i in range(2, int(n**0.5) + 1))
                result.result_data = {"result": is_prime, "operation": "prime_check", "n": n}

            elif operation == "prime_factors":
                n = payload.get("n", 12)
                factors = []
                d = 2
                while d * d <= n:
                    while n % d == 0:
                        factors.append(d)
                        n //= d
                    d += 1
                if n > 1:
                    factors.append(n)
                result.result_data = {"factors": factors, "operation": "prime_factors"}

            elif operation == "gcd":
                a = payload.get("a", 12)
                b = payload.get("b", 18)
                while b:
                    a, b = b, a % b
                result.result_data = {"result": a, "operation": "gcd"}

            elif operation == "matrix_multiply":
                # Simple 2x2 matrix multiplication
                m1 = payload.get("m1", [[1, 0], [0, 1]])
                m2 = payload.get("m2", [[1, 0], [0, 1]])
                result_matrix = [
                    [
                        sum(m1[i][k] * m2[k][j] for k in range(len(m1[0])))
                        for j in range(len(m2[0]))
                    ]
                    for i in range(len(m1))
                ]
                result.result_data = {"result": result_matrix, "operation": "matrix_multiply"}

            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown compute operation: {operation}"
                return result

            result.status = TaskStatus.COMPLETED

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Compute task {spec.task_id} failed: {e}")

        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        return result


class BenchmarkHandler(TaskHandler):
    """
    Handler for benchmark tasks.

    FOGBURST-004: Performance benchmarking.
    """

    @property
    def task_type(self) -> str:
        return "benchmark"

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute benchmark task."""
        start_time = datetime.now(UTC)
        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        payload = spec.payload
        benchmark_type = payload.get("type", "cpu")

        try:
            if benchmark_type == "cpu":
                result = await self._cpu_benchmark(result, payload)

            elif benchmark_type == "memory":
                result = await self._memory_benchmark(result, payload)

            elif benchmark_type == "io":
                result = await self._io_benchmark(result, payload)

            else:
                result.status = TaskStatus.FAILED
                result.error_message = f"Unknown benchmark type: {benchmark_type}"
                return result

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Benchmark task {spec.task_id} failed: {e}")

        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        return result

    async def _cpu_benchmark(
        self,
        result: TaskResult,
        payload: dict
    ) -> TaskResult:
        """Run CPU benchmark."""
        iterations = payload.get("iterations", 1000000)

        start = time.perf_counter()
        total = 0
        for i in range(iterations):
            total += i * i
        elapsed = time.perf_counter() - start

        result.result_data = {
            "type": "cpu",
            "iterations": iterations,
            "elapsed_seconds": round(elapsed, 4),
            "operations_per_second": round(iterations / elapsed, 2),
            "checksum": total % (10**9 + 7),
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _memory_benchmark(
        self,
        result: TaskResult,
        payload: dict
    ) -> TaskResult:
        """Run memory benchmark."""
        size_mb = payload.get("size_mb", 10)
        iterations = payload.get("iterations", 100)

        # Allocate and access memory
        start = time.perf_counter()
        for _ in range(iterations):
            data = bytearray(size_mb * 1024 * 1024)
            # Touch all memory pages
            for i in range(0, len(data), 4096):
                data[i] = i % 256
        elapsed = time.perf_counter() - start

        result.result_data = {
            "type": "memory",
            "size_mb": size_mb,
            "iterations": iterations,
            "elapsed_seconds": round(elapsed, 4),
            "throughput_mb_per_sec": round((size_mb * iterations) / elapsed, 2),
        }
        result.status = TaskStatus.COMPLETED

        return result

    async def _io_benchmark(
        self,
        result: TaskResult,
        payload: dict
    ) -> TaskResult:
        """Run I/O benchmark (async sleep simulation)."""
        iterations = payload.get("iterations", 100)
        delay_ms = payload.get("delay_ms", 10)

        start = time.perf_counter()
        for _ in range(iterations):
            await asyncio.sleep(delay_ms / 1000)
        elapsed = time.perf_counter() - start

        result.result_data = {
            "type": "io",
            "iterations": iterations,
            "delay_ms": delay_ms,
            "elapsed_seconds": round(elapsed, 4),
            "overhead_percent": round(
                ((elapsed - (iterations * delay_ms / 1000)) / elapsed) * 100, 2
            ),
        }
        result.status = TaskStatus.COMPLETED

        return result


class HealthCheckHandler(TaskHandler):
    """
    Handler for health check tasks.

    FOGBURST-004: System health verification.
    """

    @property
    def task_type(self) -> str:
        return "health_check"

    async def execute(self, spec: TaskSpec) -> TaskResult:
        """Execute health check task."""
        start_time = datetime.now(UTC)
        result = TaskResult(
            task_id=spec.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            result.result_data = {
                "status": "healthy",
                "platform": platform.system(),
                "platform_release": platform.release(),
                "python_version": platform.python_version(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": round(memory.available / (1024 * 1024), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except ImportError:
            # psutil not available, basic health check
            result.result_data = {
                "status": "healthy",
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "timestamp": datetime.now(UTC).isoformat(),
                "note": "Limited metrics (psutil not available)",
            }

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Health check failed: {e}")
            return result

        result.status = TaskStatus.COMPLETED
        result.completed_at = datetime.now(UTC)
        result.execution_time_ms = int(
            (result.completed_at - start_time).total_seconds() * 1000
        )

        return result


# Handler registry
HANDLERS: dict[str, type[TaskHandler]] = {
    "compute": ComputeHandler,
    "benchmark": BenchmarkHandler,
    "health_check": HealthCheckHandler,
}


def get_handler(task_type: str) -> Optional[TaskHandler]:
    """
    Get handler instance for task type.

    Args:
        task_type: Type of task

    Returns:
        Handler instance or None
    """
    handler_class = HANDLERS.get(task_type)
    if handler_class:
        return handler_class()
    return None


def register_handler(handler_class: type[TaskHandler]) -> None:
    """
    Register a custom task handler.

    Args:
        handler_class: Handler class to register
    """
    instance = handler_class()
    HANDLERS[instance.task_type] = handler_class
    logger.info(f"Registered handler for task type: {instance.task_type}")
