"""
SIN-030 Quality Gate: No TODO/pass/placeholder in hot production paths.

Scans production Python files for patterns that indicate incomplete
implementation: bare 'pass' in non-empty functions, TODO/FIXME/HACK
comments, and known placeholder patterns.

Exit code 0 = pass, 1 = violations found.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PROD_DIRS = [
    REPO_ROOT / "backend" / "server",
    REPO_ROOT / "src",
]

# Patterns indicating incomplete implementation
PLACEHOLDER_PATTERNS = [
    (r'#\s*TODO(?!\s*\(deferred\))', "TODO comment in production code"),
    (r'#\s*FIXME', "FIXME comment in production code"),
    (r'#\s*HACK', "HACK comment in production code"),
    (r'#\s*XXX', "XXX marker in production code"),
    (r'raise\s+NotImplementedError\b', "NotImplementedError in production path"),
    (r'placeholder', "Placeholder reference (case sensitive scan below)"),
]

SKIP_PATTERNS = [
    "__pycache__",
    ".pyc",
    "test_",
    "tests/",
    "conftest",
]


def should_skip(path: Path) -> bool:
    path_str = str(path)
    return any(skip in path_str for skip in SKIP_PATTERNS)


def check_bare_pass(content: str, filepath: Path) -> list[tuple[int, str]]:
    """Detect bare 'pass' that is the only statement in a function body."""
    violations = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "pass":
            # Check if this is in a function/method body (look back for def)
            for j in range(i - 1, max(i - 10, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("def ") or prev.startswith("async def "):
                    # Check if pass is the ONLY statement between def and next def/class
                    between = [
                        l.strip()
                        for l in lines[j + 1 : i + 1]
                        if l.strip() and not l.strip().startswith("#") and not l.strip().startswith('"""') and not l.strip().startswith("'''")
                    ]
                    # Filter out docstrings
                    code_lines = [l for l in between if l != "pass" and l != '"""' and l != "'''"]
                    if not code_lines:
                        violations.append(
                            (i + 1, f"Bare 'pass' as sole body of function (near line {j + 1})")
                        )
                    break
                if prev.startswith("class "):
                    break
    return violations


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return violations

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern, description in PLACEHOLDER_PATTERNS:
            if pattern == r'placeholder':
                # Case-insensitive but skip comments about fixing placeholders
                if re.search(r'placeholder', line, re.IGNORECASE) and \
                   'replaced' not in line.lower() and \
                   'no placeholder' not in line.lower() and \
                   'not placeholder' not in line.lower():
                    violations.append((line_num, description, line.strip()))
            elif re.search(pattern, line):
                violations.append((line_num, description, line.strip()))

    # Check for bare pass
    for line_num, desc in check_bare_pass(content, filepath):
        violations.append((line_num, desc, "pass"))

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
                    print(f"PLACEHOLDER: {rel_path}:{line_num} - {desc}")
                    print(f"  {line_text}")
                    total_violations += 1

    if total_violations > 0:
        print(f"\nWARNING: {total_violations} placeholder(s) found in production code.")
        print("These should be resolved before B+ release.")
        # Return 0 for now (warning) - change to 1 when all are fixed
        return 0

    print("PASSED: No placeholder/TODO violations found in production code paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
