# Quality Panel Tests - Quick Start Guide

**Quick reference for running and understanding Quality Panel tests**

---

## File Locations

```
tests/
├── e2e/
│   ├── page-objects/
│   │   └── QualityPanelPage.ts          # Page Object Model (287 lines)
│   └── test_quality_panel_flow.spec.ts  # E2E Tests (678 lines, 42 tests)
├── integration/
│   └── test_quality_panel.py            # Integration Tests (489 lines, 28 tests)
└── QUALITY-PANEL-TEST-SUMMARY.md        # Detailed documentation
```

---

## Quick Commands

### Run All Quality Panel Tests

```bash
# E2E tests
npm run test:e2e -- test_quality_panel_flow

# Integration tests
pytest tests/integration/test_quality_panel.py -v

# Run both
npm run test:e2e -- test_quality_panel_flow && pytest tests/integration/test_quality_panel.py
```

### Run Specific Test Suites

```bash
# E2E: Panel initialization only
npx playwright test test_quality_panel_flow -g "QP-01"

# E2E: Accessibility tests only
npx playwright test test_quality_panel_flow -g "QP-07"

# Integration: API tests only
pytest tests/integration/test_quality_panel.py::TestQualityPanelAPI -v

# Integration: Performance tests only
pytest tests/integration/test_quality_panel.py::TestQualityPanelPerformance -v
```

### Debug and Troubleshooting

```bash
# E2E with UI mode (interactive)
npx playwright test test_quality_panel_flow --ui

# E2E with headed browser
npx playwright test test_quality_panel_flow --headed

# E2E with debug mode (step through)
npx playwright test test_quality_panel_flow --debug

# Integration with verbose output
pytest tests/integration/test_quality_panel.py -vv -s

# Integration with specific test
pytest tests/integration/test_quality_panel.py::TestQualityPanelAPI::test_run_all_tests_endpoint -v
```

---

## Test Categories

### E2E Tests (42 tests)

| Category | Count | Focus |
|----------|-------|-------|
| QP-01: Initialization | 4 | Panel rendering, component visibility |
| QP-02: Test Suite Selection | 2 | Dropdown interaction, control states |
| QP-03: Test Execution | 6 | Button clicks, workflow triggers |
| QP-04: Console Output | 4 | Output display, state updates |
| QP-05: Error Handling | 4 | Failures, recovery, retries |
| QP-06: Performance | 4 | Render time, large output, memory |
| QP-07: Accessibility | 6 | WCAG 2.1 AA, keyboard, screen readers |
| QP-08: User Flows | 4 | Complete workflows, sequences |
| QP-09: Edge Cases | 4 | Boundaries, missing backend, resize |

### Integration Tests (28 tests)

| Class | Count | Focus |
|-------|-------|-------|
| TestQualityPanelAPI | 7 | API endpoints, test/benchmark execution |
| TestQualityPanelStateManagement | 5 | State transitions, output accumulation |
| TestQualityPanelPerformance | 4 | Concurrency, streaming, timeouts |
| TestQualityPanelDataPersistence | 3 | Database operations, history |
| TestQualityPanelErrorRecovery | 4 | Crash recovery, network failures |
| TestQualityPanelIntegration | 3 | End-to-end backend flows |

---

## Common Test Scenarios

### Scenario 1: Verify Panel Renders Correctly

```bash
npx playwright test test_quality_panel_flow -g "should display quality panel with all components"
```

**What it tests**: Panel visibility, title, dropdown, buttons, console

### Scenario 2: Test Execution Workflow

```bash
npx playwright test test_quality_panel_flow -g "QP-08.*complete full test execution"
```

**What it tests**: Select suite → Run tests → View output → Verify completion

### Scenario 3: Accessibility Compliance

```bash
npx playwright test test_quality_panel_flow -g "QP-07"
```

**What it tests**: Axe audit, keyboard navigation, ARIA labels, color contrast

### Scenario 4: Error Handling

```bash
npx playwright test test_quality_panel_flow -g "QP-05"
```

**What it tests**: Test failures, network errors, timeouts, recovery

### Scenario 5: Backend API Integration

```bash
pytest tests/integration/test_quality_panel.py::TestQualityPanelAPI -v
```

**What it tests**: Test execution API, benchmark API, error responses

---

## Prerequisites

### For E2E Tests

```bash
# Install dependencies
npm install

# Install Playwright browsers
npx playwright install

# Start backend (if testing with real API)
cd backend && python -m uvicorn server.main:app --port 8000

# Start frontend (in another terminal)
cd apps/control-panel && npm run dev
```

### For Integration Tests

```bash
# Install Python dependencies
pip install pytest pytest-asyncio pytest-cov

# No backend needed (tests are mocked)
```

---

## Expected Results

### E2E Tests
- **Browser**: Opens automatically (Chromium by default)
- **Duration**: 5-10 minutes for full suite
- **Pass Rate**: 38-42/42 (depending on backend availability)
- **Reports**: `tests/output/playwright-report/index.html`

### Integration Tests
- **Duration**: 1-2 minutes
- **Pass Rate**: 28/28 (all mocked, should always pass)
- **Coverage**: HTML report in `tests/output/coverage/html/index.html`

---

## Viewing Test Reports

### E2E Reports

```bash
# Generate and open HTML report
npx playwright show-report tests/output/playwright-report

# View traces for failed tests
npx playwright show-trace tests/output/playwright-artifacts/trace.zip
```

### Integration Reports

```bash
# Generate coverage report
pytest tests/integration/test_quality_panel.py --cov=backend --cov-report=html

# Open coverage report
open tests/output/coverage/html/index.html  # macOS
xdg-open tests/output/coverage/html/index.html  # Linux
start tests/output/coverage/html/index.html  # Windows
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Quality Panel Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          npm install
          npx playwright install --with-deps
          pip install -r requirements.txt

      - name: Run Integration Tests
        run: pytest tests/integration/test_quality_panel.py -v --cov=backend

      - name: Run E2E Tests
        run: npm run test:e2e -- test_quality_panel_flow

      - name: Upload test artifacts
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: tests/output/
```

---

## Troubleshooting

### E2E Tests Failing

**Problem**: Tests timeout or fail to find elements

**Solutions**:
1. Check if backend is running: `curl http://localhost:8000/health`
2. Check if frontend is running: `curl http://localhost:3000`
3. Increase timeout: Add `timeout: 30000` to test
4. Run with headed browser: `npx playwright test --headed`

### Integration Tests Failing

**Problem**: Import errors or async issues

**Solutions**:
1. Verify pytest plugins installed: `pip list | grep pytest`
2. Check pytest.ini configuration
3. Run with verbose output: `pytest -vv -s`
4. Check Python version: `python --version` (needs 3.8+)

### Accessibility Tests Failing

**Problem**: Axe violations detected

**Solutions**:
1. Run specific test: `npx playwright test -g "pass axe"`
2. View detailed report in HTML output
3. Fix violations in component code
4. Re-run: `npx playwright test -g "QP-07"`

---

## Test Data

### Mock Test Results

```typescript
// Used in E2E tests
const mockTestResult = {
  status: 'success',
  total: 313,
  passed: 310,
  failed: 3,
  duration: 45.2,
  output: ['Running tests...', 'PASS: 310/313']
};
```

### Mock Benchmark Results

```typescript
const mockBenchmarks = {
  status: 'success',
  benchmarks: [
    { name: 'network_latency', value: 12.5, unit: 'ms' },
    { name: 'throughput', value: 1500, unit: 'req/s' },
  ],
  duration: 60.0
};
```

---

## Key Test Patterns

### Page Object Pattern (E2E)

```typescript
const qualityPanel = new QualityPanelPage(page);
await qualityPanel.goto();
await qualityPanel.selectTestSuite('rust');
await qualityPanel.clickRunTests();
await qualityPanel.verifyPanelVisible();
```

### Async Testing (Integration)

```python
@pytest.mark.asyncio
async def test_run_all_tests_endpoint(mock_test_runner):
    result = await mock_test_runner.run_tests('all')
    assert result['status'] == 'success'
```

### Accessibility Testing

```typescript
await injectAxe(page);
await checkA11y(page, '.glass.rounded-xl');
```

---

## Performance Benchmarks

| Metric | Target | Test |
|--------|--------|------|
| Panel Render | <200ms | QP-06: render within budget |
| Large Output | <1s for 10k lines | Integration: streaming performance |
| Memory Usage | <1MB for 1k lines | Integration: buffer efficiency |
| API Response | <500ms | Integration: test execution |

---

## Contacts and Support

**Issue Tracker**: Check test output for detailed error messages
**Documentation**: See `QUALITY-PANEL-TEST-SUMMARY.md` for full details
**Test Updates**: Update page object if UI changes

---

## Quick Reference Card

```bash
# Most Common Commands

# Run all Quality Panel tests
npm run test:e2e -- test_quality_panel_flow
pytest tests/integration/test_quality_panel.py

# Debug failing test
npx playwright test test_quality_panel_flow --ui --grep "test name"
pytest tests/integration/test_quality_panel.py::test_name -vv

# Check accessibility
npx playwright test test_quality_panel_flow -g "QP-07"

# View reports
npx playwright show-report tests/output/playwright-report
open tests/output/coverage/html/index.html
```

---

**Last Updated**: 2025-11-25
**Test Suite Version**: 1.0.0
**Total Tests**: 70 (42 E2E + 28 Integration)
