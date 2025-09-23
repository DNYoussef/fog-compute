#!/bin/bash

echo "=========================================="
echo "Fog-Compute Test Suite Validation"
echo "=========================================="
echo ""

# Check directory structure
echo "✓ Checking test directory structure..."
[ -d "tests/rust" ] && echo "  ✓ Rust tests directory exists"
[ -d "tests/typescript" ] && echo "  ✓ TypeScript tests directory exists"
[ -d "tests/python" ] && echo "  ✓ Python tests directory exists"
[ -d "tests/e2e" ] && echo "  ✓ E2E tests directory exists"
[ -d "tests/performance" ] && echo "  ✓ Performance tests directory exists"

echo ""

# Check test files
echo "✓ Checking test files..."
[ -f "tests/rust/betanet_unit_tests.rs" ] && echo "  ✓ Rust unit tests exist"
[ -f "tests/rust/betanet_integration_tests.rs" ] && echo "  ✓ Rust integration tests exist"
[ -f "tests/typescript/components.test.tsx" ] && echo "  ✓ TypeScript component tests exist"
[ -f "tests/typescript/hooks.test.ts" ] && echo "  ✓ TypeScript hooks tests exist"
[ -f "tests/typescript/protocol.test.ts" ] && echo "  ✓ TypeScript protocol tests exist"
[ -f "tests/python/test_benchmarks.py" ] && echo "  ✓ Python benchmark tests exist"
[ -f "tests/python/test_fog_api.py" ] && echo "  ✓ Python API tests exist"
[ -f "tests/python/test_performance_metrics.py" ] && echo "  ✓ Python performance tests exist"
[ -f "tests/e2e/control-panel.spec.ts" ] && echo "  ✓ E2E control panel tests exist"
[ -f "tests/e2e/mobile.spec.ts" ] && echo "  ✓ E2E mobile tests exist"
[ -f "tests/e2e/cross-browser.spec.ts" ] && echo "  ✓ E2E cross-browser tests exist"
[ -f "tests/performance/system_test.py" ] && echo "  ✓ System performance tests exist"
[ -f "tests/performance/network_test.rs" ] && echo "  ✓ Network performance tests exist"

echo ""

# Check configuration files
echo "✓ Checking configuration files..."
[ -f "jest.config.js" ] && echo "  ✓ Jest configuration exists"
[ -f "pytest.ini" ] && echo "  ✓ Pytest configuration exists"
[ -f "playwright.config.ts" ] && echo "  ✓ Playwright configuration exists"
[ -f "tests/rust/Cargo.toml" ] && echo "  ✓ Rust test configuration exists"
[ -f "tests/setup.ts" ] && echo "  ✓ Jest setup file exists"

echo ""

# Count test files
echo "✓ Test file statistics..."
rust_tests=$(find tests/rust -name "*.rs" -type f | wc -l)
ts_tests=$(find tests/typescript -name "*.ts*" -type f | wc -l)
py_tests=$(find tests/python -name "test_*.py" -type f | wc -l)
e2e_tests=$(find tests/e2e -name "*.spec.ts" -type f | wc -l)
perf_tests=$(find tests/performance -type f \( -name "*.py" -o -name "*.rs" \) | wc -l)

echo "  → Rust test files: $rust_tests"
echo "  → TypeScript test files: $ts_tests"
echo "  → Python test files: $py_tests"
echo "  → E2E test files: $e2e_tests"
echo "  → Performance test files: $perf_tests"
total=$((rust_tests + ts_tests + py_tests + e2e_tests + perf_tests))
echo "  → Total test files: $total"

echo ""

# Check package.json scripts
echo "✓ Checking npm test scripts..."
if grep -q "test:all" package.json; then echo "  ✓ test:all script exists"; fi
if grep -q "test:rust" package.json; then echo "  ✓ test:rust script exists"; fi
if grep -q "test:python" package.json; then echo "  ✓ test:python script exists"; fi
if grep -q "test:e2e" package.json; then echo "  ✓ test:e2e script exists"; fi
if grep -q "test:coverage" package.json; then echo "  ✓ test:coverage script exists"; fi

echo ""
echo "=========================================="
echo "Validation Complete!"
echo "=========================================="
