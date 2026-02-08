"""
Phase 7 contract tests: Benchmarks, scheduler, and UI truthfulness (SIN-025..SIN-029).

Validates:
- SIN-025: Benchmark API returns real metrics, not static zeros
- SIN-026: Frontend mock fallbacks restricted (tested via source inspection)
- SIN-027: FogMap uses topology API, not hardcoded nodes (tested via source inspection)
- SIN-028: Scheduler uses pluggable ExecutionAdapter, not inline random
- SIN-029: Demo benchmark mode labeled and blocked in production
"""
import asyncio
import os
import re
import sys
from pathlib import Path

import pytest

# Ensure project roots are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_MOCKS", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-benchmarks-tests-32chars!")


# ---------------------------------------------------------------------------
# SIN-025: Benchmark API returns real metrics
# ---------------------------------------------------------------------------
class TestBenchmarkAPIReal:
    """SIN-025: Benchmark API must use real metric collectors."""

    def test_source_no_static_mock_comment(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "backend"
            / "server"
            / "routes"
            / "benchmarks.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "return mock data" not in source.lower()

    def test_source_uses_psutil(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "backend"
            / "server"
            / "routes"
            / "benchmarks.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "psutil" in source
        assert "cpu_percent" in source
        assert "virtual_memory" in source

    def test_source_reports_data_source(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "backend"
            / "server"
            / "routes"
            / "benchmarks.py"
        )
        source = source_path.read_text(encoding="utf-8")
        # Endpoint must declare its data source
        assert '"source"' in source

    def test_stop_benchmark_validates_id(self):
        source_path = (
            Path(__file__).resolve().parents[2]
            / "backend"
            / "server"
            / "routes"
            / "benchmarks.py"
        )
        source = source_path.read_text(encoding="utf-8")
        # Stop must not blindly return success for unknown IDs
        assert "404" in source or "not found" in source.lower()


# ---------------------------------------------------------------------------
# SIN-026: Frontend mock fallbacks restricted to dev
# ---------------------------------------------------------------------------
class TestFrontendMockGating:
    """SIN-026: Frontend API routes must gate mock fallbacks on NODE_ENV."""

    def _read_ts(self, rel_path: str) -> str:
        source_path = Path(__file__).resolve().parents[2] / rel_path
        return source_path.read_text(encoding="utf-8")

    def test_dashboard_stats_has_production_guard(self):
        source = self._read_ts(
            "apps/control-panel/app/api/dashboard/stats/route.ts"
        )
        assert "NODE_ENV" in source or "isProduction" in source
        assert "_mock" in source

    def test_dashboard_stats_returns_503_in_production(self):
        source = self._read_ts(
            "apps/control-panel/app/api/dashboard/stats/route.ts"
        )
        assert "503" in source

    def test_benchmarks_data_has_production_guard(self):
        source = self._read_ts(
            "apps/control-panel/app/api/benchmarks/data/route.ts"
        )
        assert "NODE_ENV" in source or "isProduction" in source
        assert "_mock" in source

    def test_benchmarks_data_returns_503_in_production(self):
        source = self._read_ts(
            "apps/control-panel/app/api/benchmarks/data/route.ts"
        )
        assert "503" in source


# ---------------------------------------------------------------------------
# SIN-027: FogMap uses topology API
# ---------------------------------------------------------------------------
class TestFogMapTopology:
    """SIN-027: FogMap must fetch from topology API, not hardcoded data."""

    def _read_tsx(self) -> str:
        source_path = (
            Path(__file__).resolve().parents[2]
            / "apps"
            / "control-panel"
            / "components"
            / "FogMap.tsx"
        )
        return source_path.read_text(encoding="utf-8")

    def test_no_hardcoded_mock_nodes(self):
        source = self._read_tsx()
        assert "mockNodes" not in source

    def test_fetches_topology_api(self):
        source = self._read_tsx()
        assert "topology" in source.lower()
        assert "fetch(" in source

    def test_has_stale_data_indicator(self):
        source = self._read_tsx()
        assert "unavailable" in source.lower()


# ---------------------------------------------------------------------------
# SIN-028: Scheduler ExecutionAdapter
# ---------------------------------------------------------------------------
class TestSchedulerExecutionAdapter:
    """SIN-028: Scheduler must use pluggable ExecutionAdapter."""

    def test_execution_adapter_class_exists(self):
        from scheduler.intelligent_scheduler import ExecutionAdapter
        assert hasattr(ExecutionAdapter, "execute")

    def test_stub_adapter_exists(self):
        from scheduler.intelligent_scheduler import StubExecutionAdapter
        adapter = StubExecutionAdapter(fixed_time=0.01, success=True)
        assert adapter.fixed_time == 0.01

    def test_stub_adapter_is_deterministic(self):
        from scheduler.intelligent_scheduler import (
            StubExecutionAdapter,
            TaskMetadata,
            TaskPriority,
            ResourceRequirements,
            WorkerNode,
            ResourceType,
        )

        adapter = StubExecutionAdapter(fixed_time=0.01, success=True)

        task = TaskMetadata(
            task_id="test-1",
            priority=TaskPriority.MEDIUM,
            requirements=ResourceRequirements(),
        )
        worker = WorkerNode(
            worker_id="w1",
            available_cpu=4.0,
            available_memory_mb=4096,
            available_gpu=0,
            capabilities={ResourceType.CPU, ResourceType.MEMORY},
        )

        exec_time, success = asyncio.get_event_loop().run_until_complete(
            adapter.execute(task, worker)
        )
        assert exec_time == 0.01
        assert success is True

    def test_simulated_adapter_blocked_in_production(self):
        from scheduler.intelligent_scheduler import (
            SimulatedExecutionAdapter,
            TaskMetadata,
            TaskPriority,
            ResourceRequirements,
            WorkerNode,
            ResourceType,
        )

        adapter = SimulatedExecutionAdapter()
        task = TaskMetadata(
            task_id="test-1",
            priority=TaskPriority.MEDIUM,
            requirements=ResourceRequirements(),
        )
        worker = WorkerNode(
            worker_id="w1",
            available_cpu=4.0,
            available_memory_mb=4096,
            available_gpu=0,
            capabilities={ResourceType.CPU, ResourceType.MEMORY},
        )

        old_env = os.environ.get("APP_ENV")
        os.environ["APP_ENV"] = "production"
        try:
            with pytest.raises(RuntimeError, match="production"):
                asyncio.get_event_loop().run_until_complete(
                    adapter.execute(task, worker)
                )
        finally:
            if old_env is not None:
                os.environ["APP_ENV"] = old_env
            else:
                os.environ.pop("APP_ENV", None)

    def test_scheduler_accepts_custom_adapter(self):
        from scheduler.intelligent_scheduler import (
            IntelligentScheduler,
            StubExecutionAdapter,
        )

        adapter = StubExecutionAdapter(fixed_time=0.01)
        scheduler = IntelligentScheduler(execution_adapter=adapter)
        assert scheduler._executor is adapter

    def test_execute_task_no_inline_random(self):
        """The _execute_task method must not contain inline random calls."""
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "scheduler"
            / "intelligent_scheduler.py"
        )
        source = source_path.read_text(encoding="utf-8")
        match = re.search(
            r"async def _execute_task\(.*?\).*?(?=\n    async def |\n    def |\nclass )",
            source,
            re.DOTALL,
        )
        assert match, "_execute_task method not found"
        method_body = match.group()
        assert "random.uniform" not in method_body
        assert "random.random()" not in method_body


# ---------------------------------------------------------------------------
# SIN-029: Demo benchmark mode labeled and blocked in production
# ---------------------------------------------------------------------------
class TestDemoBenchmarkLabeling:
    """SIN-029: Demo mode must be clearly labeled and blocked in production."""

    def _read_source(self) -> str:
        source_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "fog"
            / "benchmarks"
            / "run_benchmarks.py"
        )
        return source_path.read_text(encoding="utf-8")

    def test_demo_mode_has_is_demo_flag(self):
        source = self._read_source()
        assert "is_demo" in source

    def test_demo_mode_has_warning(self):
        source = self._read_source()
        assert "SIMULATED" in source

    def test_demo_mode_checks_app_env(self):
        source = self._read_source()
        # Must check APP_ENV in run_demo_mode
        match = re.search(
            r"async def run_demo_mode\(.*?\).*?(?=\n    async def |\n    def |\nclass )",
            source,
            re.DOTALL,
        )
        assert match, "run_demo_mode method not found"
        method_body = match.group()
        assert "APP_ENV" in method_body or "production" in method_body

    def test_demo_mode_returns_error_in_production(self):
        source = self._read_source()
        match = re.search(
            r"async def run_demo_mode\(.*?\).*?(?=\n    async def |\n    def |\nclass )",
            source,
            re.DOTALL,
        )
        assert match
        method_body = match.group()
        assert '"success": False' in method_body or "'success': False" in method_body
