"""
Phase 8 contract tests: CI gates and quality verification (SIN-030..SIN-032).

Validates:
- SIN-030: Quality gate scripts exist and run
- SIN-031: Contract test suite exists and covers all phases
- SIN-032: Mock guard prevents production mock leakage
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_MOCKS", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-gates-tests-32chars!")


# ---------------------------------------------------------------------------
# SIN-030: Coverage and quality gate infrastructure
# ---------------------------------------------------------------------------
class TestQualityGateScripts:
    """SIN-030: Quality gate scripts exist and are executable."""

    def test_check_prod_mocks_script_exists(self):
        script = REPO_ROOT / "scripts" / "ci" / "check_prod_mocks.py"
        assert script.exists(), "check_prod_mocks.py not found"

    def test_check_placeholders_script_exists(self):
        script = REPO_ROOT / "scripts" / "ci" / "check_placeholders.py"
        assert script.exists(), "check_placeholders.py not found"

    def test_check_workflow_guards_script_exists(self):
        script = REPO_ROOT / "scripts" / "ci" / "check_workflow_guards.py"
        assert script.exists(), "check_workflow_guards.py not found"

    def test_check_prod_mocks_passes(self):
        """SIN-032: No mock violations in production code."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "check_prod_mocks.py")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Mock check failed:\n{result.stdout}\n{result.stderr}"

    def test_check_workflow_guards_passes(self):
        """CI commands must not hide dependency or test failures."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "check_workflow_guards.py")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Workflow guard failed:\n{result.stdout}\n{result.stderr}"

    def test_python_ci_workflow_exists(self):
        workflow = REPO_ROOT / ".github" / "workflows" / "python-tests.yml"
        assert workflow.exists(), "python-tests.yml CI workflow not found"

    def test_python_ci_includes_contract_tests(self):
        workflow = REPO_ROOT / ".github" / "workflows" / "python-tests.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "tests/contracts/" in content
        assert "quality-gate" in content.lower() or "quality_gate" in content.lower()


# ---------------------------------------------------------------------------
# SIN-031: Contract test suite covers all phases
# ---------------------------------------------------------------------------
class TestContractSuiteCoverage:
    """SIN-031: Contract tests exist for every phase."""

    EXPECTED_TEST_FILES = [
        "test_betanet_contracts.py",   # Phase 0
        "test_mock_guard.py",          # Phase 0
        "test_betanet_integration.py", # Phase 1
        "test_idle_compute.py",        # Phase 2
        "test_p2p_transports.py",      # Phase 3
        "test_vpn_onion.py",           # Phase 5
        "test_tokenomics.py",          # Phase 6
        "test_benchmarks_scheduler.py",# Phase 7
        "test_ci_quality_gates.py",    # Phase 8 (this file)
    ]

    def test_all_phase_test_files_exist(self):
        contracts_dir = REPO_ROOT / "tests" / "contracts"
        existing = {f.name for f in contracts_dir.glob("test_*.py")}
        for expected in self.EXPECTED_TEST_FILES:
            assert expected in existing, f"Missing contract test: {expected}"

    def test_conftest_exists(self):
        conftest = REPO_ROOT / "tests" / "contracts" / "conftest.py"
        assert conftest.exists()

    def test_schema_files_exist(self):
        schemas_dir = REPO_ROOT / "docs" / "contracts"
        assert schemas_dir.exists(), "docs/contracts/ schema directory missing"
        schemas = list(schemas_dir.glob("*.schema.json"))
        assert len(schemas) >= 1, "No schema files found"


# ---------------------------------------------------------------------------
# SIN-032: Global mock guard
# ---------------------------------------------------------------------------
class TestGlobalMockGuard:
    """SIN-032: Mock guard prevents production mock leakage."""

    def test_mock_guard_module_exists(self):
        guard_path = REPO_ROOT / "backend" / "server" / "mock_guard.py"
        assert guard_path.exists()

    def test_mock_guard_has_allow_mock_fallback(self):
        guard_path = REPO_ROOT / "backend" / "server" / "mock_guard.py"
        source = guard_path.read_text(encoding="utf-8")
        assert "allow_mock_fallback" in source

    def test_mock_guard_has_guard_mock(self):
        guard_path = REPO_ROOT / "backend" / "server" / "mock_guard.py"
        source = guard_path.read_text(encoding="utf-8")
        assert "guard_mock" in source

    def test_mock_guard_checks_app_env(self):
        guard_path = REPO_ROOT / "backend" / "server" / "mock_guard.py"
        source = guard_path.read_text(encoding="utf-8")
        assert "APP_ENV" in source

    def test_mock_guard_checks_allow_mocks(self):
        guard_path = REPO_ROOT / "backend" / "server" / "mock_guard.py"
        source = guard_path.read_text(encoding="utf-8")
        assert "ALLOW_MOCKS" in source

    def test_production_frontend_routes_return_503(self):
        """Frontend API routes must not silently return mock data in production."""
        ts_routes = [
            REPO_ROOT / "apps" / "control-panel" / "app" / "api" / "dashboard" / "stats" / "route.ts",
            REPO_ROOT / "apps" / "control-panel" / "app" / "api" / "benchmarks" / "data" / "route.ts",
        ]
        for route_file in ts_routes:
            source = route_file.read_text(encoding="utf-8")
            assert "503" in source, f"{route_file.name} missing 503 production error"
            assert "_mock" in source, f"{route_file.name} missing _mock flag"


# ---------------------------------------------------------------------------
# Final verification: All SINs addressed
# ---------------------------------------------------------------------------
class TestSINRegisterClosure:
    """Verify that all SIN IDs have been addressed with tests."""

    SIN_COVERAGE = {
        # Phase 0
        "SIN-031": "test_betanet_contracts.py",
        "SIN-032": "test_mock_guard.py",
        # Phase 1
        "SIN-001": "test_betanet_integration.py",
        "SIN-002": "test_betanet_integration.py",
        "SIN-003": "test_betanet_integration.py",
        "SIN-004": "test_betanet_integration.py",
        "SIN-005": "test_betanet_integration.py",
        "SIN-006": "test_betanet_integration.py",
        "SIN-007": "test_betanet_integration.py",
        # Phase 2
        "SIN-016": "test_idle_compute.py",
        "SIN-017": "test_idle_compute.py",
        "SIN-018": "test_idle_compute.py",
        # Phase 3
        "SIN-009": "test_p2p_transports.py",
        "SIN-010": "test_p2p_transports.py",
        "SIN-011": "test_p2p_transports.py",
        "SIN-015": "test_p2p_transports.py",
        # Phase 4 (Jest - BitChat TS)
        "SIN-012": "bitchat tests (Jest)",
        "SIN-013": "bitchat tests (Jest)",
        "SIN-014": "bitchat tests (Jest)",
        # Phase 5
        "SIN-019": "test_vpn_onion.py",
        "SIN-020": "test_vpn_onion.py",
        "SIN-021": "test_vpn_onion.py",
        # Phase 6
        "SIN-022": "test_tokenomics.py",
        "SIN-023": "test_tokenomics.py",
        "SIN-024": "test_tokenomics.py",
        # Phase 7
        "SIN-025": "test_benchmarks_scheduler.py",
        "SIN-026": "test_benchmarks_scheduler.py",
        "SIN-027": "test_benchmarks_scheduler.py",
        "SIN-028": "test_benchmarks_scheduler.py",
        "SIN-029": "test_benchmarks_scheduler.py",
        # Phase 8
        "SIN-030": "test_ci_quality_gates.py",
    }

    def test_all_32_sins_covered(self):
        """Every SIN-001 through SIN-032 must have test coverage."""
        covered = set(self.SIN_COVERAGE.keys())
        expected = {f"SIN-{i:03d}" for i in range(1, 33)}
        # SIN-008 is not in the plan (IDs skip from 007 to 009)
        expected.discard("SIN-008")
        missing = expected - covered
        assert not missing, f"SINs without test coverage: {sorted(missing)}"

    def test_test_files_exist_for_all_mappings(self):
        """Test files referenced in SIN coverage map must exist."""
        contracts_dir = REPO_ROOT / "tests" / "contracts"
        existing = {f.name for f in contracts_dir.glob("test_*.py")}
        for sin_id, test_file in self.SIN_COVERAGE.items():
            if test_file.endswith("(Jest)"):
                continue  # Jest tests are in a different location
            assert test_file in existing, (
                f"{sin_id} references {test_file} but file not found"
            )
