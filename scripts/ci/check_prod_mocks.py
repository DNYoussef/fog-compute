"""
SIN-032 Quality Gate: No mock/stub fallback in production code paths.

Scans Python source files for patterns that would silently return mock data
or fake success in production mode without proper env guards.

Exit code 0 = pass, 1 = violations found.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories containing production code (not tests, not scripts)
PROD_DIRS = [
    REPO_ROOT / "backend" / "server",
    REPO_ROOT / "src",
]

# Patterns that indicate mock data without env guards
VIOLATION_PATTERNS = [
    (r'system_key_placeholder', "Placeholder system key (SIN-023)"),
    (r'total_participants\s*=\s*10', "Hardcoded participant count (SIN-024)"),
    (r'return\s+True\s*#.*stub', "Stub returning True unconditionally"),
    (r'mock_data\s*=\s*\{', "Inline mock_data dict in production path"),
    (r'daily limit validation disabled', "Disabled daily limit (SIN-022)"),
]

# Files/dirs to skip
SKIP_PATTERNS = [
    "__pycache__",
    ".pyc",
    "test_",
    "tests/",
    "conftest",
    "mock_guard.py",  # The guard itself is allowed to reference mocks
]


def should_skip(path: Path) -> bool:
    path_str = str(path)
    return any(skip in path_str for skip in SKIP_PATTERNS)


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return violations

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, description in VIOLATION_PATTERNS:
            if re.search(pattern, line):
                violations.append((line_num, description, line.strip()))
    return violations


def main() -> int:
    total_violations = 0

    for prod_dir in PROD_DIRS:
        if not prod_dir.exists():
            continue

        for py_file in prod_dir.rglob("*.py"):
            if should_skip(py_file):
                continue

            violations = scan_file(py_file)
            if violations:
                rel_path = py_file.relative_to(REPO_ROOT)
                for line_num, desc, line_text in violations:
                    print(f"VIOLATION: {rel_path}:{line_num} - {desc}")
                    print(f"  {line_text}")
                    total_violations += 1

    if total_violations > 0:
        print(f"\nFAILED: {total_violations} mock/stub violation(s) found in production code.")
        return 1

    print("PASSED: No mock/stub violations found in production code paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
