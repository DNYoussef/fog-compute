"""
Guard CI workflows against greenwashing.

This checks for concrete failure modes that make CI look green without proving
the code works: hidden install errors, swallowed test failures, advisory Rust
lint/format gates, missing manual dispatch, and missing integration-branch
coverage.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

ACTIVE_WORKFLOWS = [
    "python-tests.yml",
    "node-tests.yml",
    "rust-tests.yml",
    "e2e-tests.yml",
]

FORBIDDEN_PATTERNS = {
    "python-tests.yml": [
        "2>/dev/null || true",
        "2>/dev/null || echo",
        "|| echo \"Backend tests directory may not exist yet\"",
    ],
    "rust-tests.yml": [
        "continue-on-error: true",
    ],
}

REQUIRED_SNIPPETS = {
    "python-tests.yml": [
        "workflow_dispatch:",
        "'integration/**'",
        "tests/contracts/ -v --tb=short -p no:cacheprovider --cov=src --cov-report=term -W error::RuntimeWarning",
        (
            "backend/tests/test_mesh_routes.py backend/tests/test_heartbeat_jitter.py "
            "backend/tests/test_control_plane.py backend/tests/test_fog_bridge_control_plane.py "
            "-v --tb=short -p no:cacheprovider --no-cov"
        ),
        "python scripts/ci/check_workflow_guards.py",
    ],
    "node-tests.yml": [
        "workflow_dispatch:",
        "'integration/**'",
    ],
    "rust-tests.yml": [
        "workflow_dispatch:",
        "'integration/**'",
        "cargo clippy",
        "cargo fmt -- --check",
    ],
    "e2e-tests.yml": [
        "workflow_dispatch:",
        "'integration/**'",
        "contents: write",
    ],
}


def main() -> int:
    violations: list[str] = []

    for workflow_name in ACTIVE_WORKFLOWS:
        workflow = WORKFLOWS / workflow_name
        if not workflow.exists():
            violations.append(f"{workflow_name}: missing active workflow")
            continue

        content = workflow.read_text(encoding="utf-8")

        for pattern in FORBIDDEN_PATTERNS.get(workflow_name, []):
            if pattern in content:
                violations.append(f"{workflow_name}: forbidden failure-masking pattern: {pattern}")

        for snippet in REQUIRED_SNIPPETS.get(workflow_name, []):
            if snippet not in content:
                violations.append(f"{workflow_name}: missing required guard: {snippet}")

    if violations:
        for violation in violations:
            print(f"WORKFLOW_GUARD: {violation}")
        print(f"\nFAILED: {len(violations)} CI workflow guard violation(s) found.")
        return 1

    print("PASSED: CI workflows fail hard on covered test and quality gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
