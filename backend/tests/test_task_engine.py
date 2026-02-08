"""
Tests for Task Execution Engine
FOGBURST-004: Task runner, handlers, and engine tests
"""
import asyncio
import pytest
from datetime import datetime, UTC

# Import task engine components
from task_engine import (
    TaskRunner,
    TaskResult,
    TaskStatus,
    TaskEngine,
    EngineConfig,
    TaskHandler,
    ComputeHandler,
    BenchmarkHandler,
    HealthCheckHandler,
)
from task_engine.runner import TaskSpec
from task_engine.handlers import get_handler, register_handler, HANDLERS


# =============================================================================
# TaskSpec Tests
# =============================================================================

class TestTaskSpec:
    """Test task specification."""

    def test_create_command_spec(self):
        """Test creating command task spec."""
        spec = TaskSpec(
            task_id="task-123",
            task_type="command",
            command="echo hello",
            timeout_sec=60,
        )
        assert spec.task_id == "task-123"
        assert spec.command == "echo hello"
        assert spec.timeout_sec == 60

    def test_create_compute_spec(self):
        """Test creating compute task spec."""
        spec = TaskSpec(
            task_id="compute-456",
            task_type="compute",
            payload={"operation": "add", "a": 5, "b": 3},
        )
        assert spec.task_type == "compute"
        assert spec.payload["operation"] == "add"

    def test_spec_to_dict(self):
        """Test spec serialization."""
        spec = TaskSpec(
            task_id="test-1",
            task_type="benchmark",
            payload={"type": "cpu", "iterations": 1000},
        )
        d = spec.to_dict()
        assert d["task_id"] == "test-1"
        assert d["task_type"] == "benchmark"
        assert d["payload"]["type"] == "cpu"


# =============================================================================
# TaskResult Tests
# =============================================================================

class TestTaskResult:
    """Test task result."""

    def test_create_result(self):
        """Test creating task result."""
        result = TaskResult(
            task_id="task-123",
            status=TaskStatus.COMPLETED,
            exit_code=0,
            result_data={"value": 42},
        )
        assert result.task_id == "task-123"
        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["value"] == 42

    def test_result_to_dict(self):
        """Test result serialization."""
        result = TaskResult(
            task_id="task-456",
            status=TaskStatus.FAILED,
            error_message="Test error",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        d = result.to_dict()
        assert d["task_id"] == "task-456"
        assert d["status"] == "failed"
        assert d["error_message"] == "Test error"
        assert "started_at" in d


# =============================================================================
# TaskRunner Tests
# =============================================================================

class TestTaskRunner:
    """Test task runner."""

    def test_init(self):
        """Test runner initialization."""
        runner = TaskRunner(
            default_timeout_sec=60,
            max_concurrent=2,
        )
        assert runner.default_timeout_sec == 60
        assert runner.max_concurrent == 2

    @pytest.mark.asyncio
    async def test_execute_compute_add(self):
        """FOGBURST-004: Test compute add operation."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="add-1",
            task_type="compute",
            payload={"operation": "add", "a": 10, "b": 5},
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 15
        assert result.result_data["operation"] == "add"

    @pytest.mark.asyncio
    async def test_execute_compute_multiply(self):
        """FOGBURST-004: Test compute multiply operation."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="mult-1",
            task_type="compute",
            payload={"operation": "multiply", "a": 7, "b": 6},
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 42

    @pytest.mark.asyncio
    async def test_execute_compute_factorial(self):
        """FOGBURST-004: Test compute factorial operation."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="fact-1",
            task_type="compute",
            payload={"operation": "factorial", "n": 5},
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 120

    @pytest.mark.asyncio
    async def test_execute_compute_fibonacci(self):
        """FOGBURST-004: Test compute fibonacci operation."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="fib-1",
            task_type="compute",
            payload={"operation": "fibonacci", "n": 10},
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 55

    @pytest.mark.asyncio
    async def test_execute_compute_prime_check(self):
        """FOGBURST-004: Test compute prime check operation."""
        runner = TaskRunner()

        # Test prime number
        spec1 = TaskSpec(
            task_id="prime-1",
            task_type="compute",
            payload={"operation": "prime_check", "n": 17},
        )
        result1 = await runner.execute(spec1)
        assert result1.result_data["result"] is True

        # Test non-prime number
        spec2 = TaskSpec(
            task_id="prime-2",
            task_type="compute",
            payload={"operation": "prime_check", "n": 15},
        )
        result2 = await runner.execute(spec2)
        assert result2.result_data["result"] is False

    @pytest.mark.asyncio
    async def test_execute_benchmark(self):
        """FOGBURST-004: Test benchmark task."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="bench-1",
            task_type="benchmark",
            payload={"iterations": 10000},
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert "iterations" in result.result_data
        assert "elapsed_seconds" in result.result_data
        assert "operations_per_second" in result.result_data

    @pytest.mark.asyncio
    async def test_execute_health_check(self):
        """FOGBURST-004: Test health check task."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="health-1",
            task_type="health_check",
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["status"] == "healthy"
        assert "platform" in result.result_data

    @pytest.mark.asyncio
    async def test_execute_unknown_type_fails(self):
        """Test unknown task type fails."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="unknown-1",
            task_type="unknown_type",
        )

        result = await runner.execute(spec)

        assert result.status == TaskStatus.FAILED
        assert "Unknown task type" in result.error_message

    @pytest.mark.asyncio
    async def test_runner_stats(self):
        """Test runner statistics."""
        runner = TaskRunner()

        spec = TaskSpec(
            task_id="stats-1",
            task_type="compute",
            payload={"operation": "add", "a": 1, "b": 1},
        )

        await runner.execute(spec)

        stats = runner.get_stats()
        assert stats["total_executed"] == 1
        assert stats["completed"] == 1


# =============================================================================
# Handler Tests
# =============================================================================

class TestComputeHandler:
    """Test compute handler."""

    def test_task_type(self):
        """Test handler task type."""
        handler = ComputeHandler()
        assert handler.task_type == "compute"

    @pytest.mark.asyncio
    async def test_execute_add(self):
        """Test add operation."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-add-1",
            task_type="compute",
            payload={"operation": "add", "a": 100, "b": 50},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 150

    @pytest.mark.asyncio
    async def test_execute_subtract(self):
        """Test subtract operation."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-sub-1",
            task_type="compute",
            payload={"operation": "subtract", "a": 100, "b": 30},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 70

    @pytest.mark.asyncio
    async def test_execute_divide(self):
        """Test divide operation."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-div-1",
            task_type="compute",
            payload={"operation": "divide", "a": 100, "b": 4},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 25.0

    @pytest.mark.asyncio
    async def test_execute_divide_by_zero(self):
        """Test divide by zero fails."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-div-0",
            task_type="compute",
            payload={"operation": "divide", "a": 100, "b": 0},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.FAILED
        assert "zero" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_power(self):
        """Test power operation."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-pow-1",
            task_type="compute",
            payload={"operation": "power", "base": 2, "exp": 10},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 1024

    @pytest.mark.asyncio
    async def test_execute_gcd(self):
        """Test GCD operation."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-gcd-1",
            task_type="compute",
            payload={"operation": "gcd", "a": 48, "b": 18},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 6

    @pytest.mark.asyncio
    async def test_execute_prime_factors(self):
        """Test prime factors operation."""
        handler = ComputeHandler()

        spec = TaskSpec(
            task_id="h-pf-1",
            task_type="compute",
            payload={"operation": "prime_factors", "n": 60},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["factors"] == [2, 2, 3, 5]


class TestBenchmarkHandler:
    """Test benchmark handler."""

    def test_task_type(self):
        """Test handler task type."""
        handler = BenchmarkHandler()
        assert handler.task_type == "benchmark"

    @pytest.mark.asyncio
    async def test_cpu_benchmark(self):
        """Test CPU benchmark."""
        handler = BenchmarkHandler()

        spec = TaskSpec(
            task_id="b-cpu-1",
            task_type="benchmark",
            payload={"type": "cpu", "iterations": 10000},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["type"] == "cpu"
        assert result.result_data["iterations"] == 10000
        assert "elapsed_seconds" in result.result_data

    @pytest.mark.asyncio
    async def test_io_benchmark(self):
        """Test I/O benchmark."""
        handler = BenchmarkHandler()

        spec = TaskSpec(
            task_id="b-io-1",
            task_type="benchmark",
            payload={"type": "io", "iterations": 10, "delay_ms": 1},
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["type"] == "io"


class TestHealthCheckHandler:
    """Test health check handler."""

    def test_task_type(self):
        """Test handler task type."""
        handler = HealthCheckHandler()
        assert handler.task_type == "health_check"

    @pytest.mark.asyncio
    async def test_execute(self):
        """Test health check execution."""
        handler = HealthCheckHandler()

        spec = TaskSpec(
            task_id="hc-1",
            task_type="health_check",
        )

        result = await handler.execute(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["status"] == "healthy"


class TestHandlerRegistry:
    """Test handler registry."""

    def test_get_handler(self):
        """Test getting handler by type."""
        handler = get_handler("compute")
        assert handler is not None
        assert isinstance(handler, ComputeHandler)

    def test_get_unknown_handler(self):
        """Test getting unknown handler."""
        handler = get_handler("nonexistent")
        assert handler is None


# =============================================================================
# TaskEngine Tests
# =============================================================================

class TestEngineConfig:
    """Test engine configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = EngineConfig()
        assert config.max_concurrent_tasks == 4
        assert config.default_timeout_sec == 300
        assert config.max_queue_size == 100

    def test_custom_config(self):
        """Test custom configuration."""
        config = EngineConfig(
            max_concurrent_tasks=8,
            default_timeout_sec=60,
            max_queue_size=50,
        )
        assert config.max_concurrent_tasks == 8
        assert config.default_timeout_sec == 60


class TestTaskEngine:
    """Test task engine."""

    def test_init(self):
        """Test engine initialization."""
        engine = TaskEngine()
        assert engine.is_running is False
        assert engine.is_paused is False

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test engine start/stop."""
        engine = TaskEngine()

        await engine.start()
        assert engine.is_running is True

        await engine.stop()
        assert engine.is_running is False

    def test_pause_resume(self):
        """Test engine pause/resume."""
        engine = TaskEngine()

        engine.pause()
        assert engine.is_paused is True

        engine.resume()
        assert engine.is_paused is False

    def test_submit_task(self):
        """Test task submission."""
        engine = TaskEngine()

        spec = TaskSpec(
            task_id="eng-1",
            task_type="compute",
            payload={"operation": "add", "a": 1, "b": 2},
        )

        result = engine.submit(spec)
        assert result is True
        assert engine.get_queue_size() == 1

    def test_submit_queue_full(self):
        """Test submission when queue is full."""
        config = EngineConfig(max_queue_size=2)
        engine = TaskEngine(config=config)

        for i in range(3):
            spec = TaskSpec(task_id=f"eng-{i}", task_type="compute")
            result = engine.submit(spec)

            if i < 2:
                assert result is True
            else:
                assert result is False  # Queue full

    @pytest.mark.asyncio
    async def test_execute_immediate(self):
        """FOGBURST-004: Test immediate task execution."""
        engine = TaskEngine()

        spec = TaskSpec(
            task_id="imm-1",
            task_type="compute",
            payload={"operation": "add", "a": 5, "b": 5},
        )

        result = await engine.execute_immediate(spec)

        assert result.status == TaskStatus.COMPLETED
        assert result.result_data["result"] == 10

    @pytest.mark.asyncio
    async def test_engine_stats(self):
        """Test engine statistics."""
        engine = TaskEngine()

        spec = TaskSpec(
            task_id="stats-1",
            task_type="compute",
            payload={"operation": "add", "a": 1, "b": 1},
        )

        await engine.execute_immediate(spec)

        stats = engine.get_stats()
        assert stats["tasks_completed"] == 1
        assert "available_handlers" in stats
        assert "compute" in stats["available_handlers"]

    def test_get_available_task_types(self):
        """Test getting available task types."""
        engine = TaskEngine()

        types = engine.get_available_task_types()

        assert "compute" in types
        assert "benchmark" in types
        assert "health_check" in types

    @pytest.mark.asyncio
    async def test_callback_on_result(self):
        """Test result callback."""
        results = []

        async def on_result(result: TaskResult):
            results.append(result)

        engine = TaskEngine(on_result=on_result)

        spec = TaskSpec(
            task_id="cb-1",
            task_type="compute",
            payload={"operation": "add", "a": 1, "b": 1},
        )

        await engine.execute_immediate(spec)

        # Callback should have been called
        assert len(results) >= 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestTaskEngineIntegration:
    """Integration tests for task engine."""

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self):
        """FOGBURST-004: Test complete task lifecycle."""
        results = []

        async def on_result(result: TaskResult):
            results.append(result)

        engine = TaskEngine(on_result=on_result)
        await engine.start()

        try:
            # Submit multiple tasks
            tasks = [
                TaskSpec(
                    task_id=f"life-{i}",
                    task_type="compute",
                    payload={"operation": "factorial", "n": i + 1},
                )
                for i in range(5)
            ]

            for spec in tasks:
                await engine.execute_immediate(spec)

            # All should complete
            assert len(results) >= 5

            # Check results
            factorials = [1, 2, 6, 24, 120]
            for i, result in enumerate(results[:5]):
                assert result.status == TaskStatus.COMPLETED
                assert result.result_data["result"] == factorials[i]

        finally:
            await engine.stop()

    @pytest.mark.asyncio
    async def test_mixed_task_types(self):
        """Test executing different task types."""
        engine = TaskEngine()

        # Compute task
        compute_result = await engine.execute_immediate(
            TaskSpec(
                task_id="mix-1",
                task_type="compute",
                payload={"operation": "add", "a": 10, "b": 20},
            )
        )
        assert compute_result.status == TaskStatus.COMPLETED
        assert compute_result.result_data["result"] == 30

        # Benchmark task
        bench_result = await engine.execute_immediate(
            TaskSpec(
                task_id="mix-2",
                task_type="benchmark",
                payload={"type": "cpu", "iterations": 1000},
            )
        )
        assert bench_result.status == TaskStatus.COMPLETED

        # Health check task
        health_result = await engine.execute_immediate(
            TaskSpec(
                task_id="mix-3",
                task_type="health_check",
            )
        )
        assert health_result.status == TaskStatus.COMPLETED
        assert health_result.result_data["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
