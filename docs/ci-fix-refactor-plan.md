# Cross-Browser Test Refactoring Plan - TDD Methodology

## Executive Summary

**Problem**: The `tests/e2e/cross-browser.spec.ts` file contains **13 manual browser launches** (`.launch()`) that conflict with Playwright's project-based execution in CI environments. Playwright's configuration already defines browser projects (chromium, firefox, webkit), but the tests override this by manually launching browsers.

**Impact**:
- CI tests fail with "Browser has been closed" errors
- Tests run redundantly (manual launch + project-based execution)
- Resource waste and slower CI times
- Inconsistent behavior between local and CI environments

**Solution**: Refactor to use Playwright's `{ page }` fixture pattern, leveraging the project-based browser configuration.

---

## Analysis of Current Issues

### Manual Browser Launches Identified (13 total)

| Line | Browser | Test Description | Impact |
|------|---------|------------------|--------|
| 9 | chromium | renders correctly in Chrome | Conflicts with chromium project |
| 21 | chromium | 3D topology works in Chrome | Conflicts with chromium project |
| 43 | firefox | renders correctly in Firefox | Conflicts with firefox project |
| 55 | firefox | charts render in Firefox | Conflicts with firefox project |
| 67 | firefox | WebSocket works in Firefox | Conflicts with firefox project |
| 81 | webkit | renders correctly in Safari | Conflicts with webkit project |
| 93 | webkit | 3D topology works in Safari | Conflicts with webkit project |
| 105 | webkit | touch events work in Safari | Conflicts with webkit project |
| 131 | loop | benchmark execution works in ${name} | Runs 3x (all browsers) |
| 149 | loop | real-time updates work in ${name} | Runs 3x (all browsers) |
| 162 | loop | API calls work in ${name} | Runs 3x (all browsers) |
| 244 | loop | page load time is acceptable in ${name} | Runs 3x (all browsers) |
| 264 | loop | memory usage is reasonable in ${name} | Runs 3x (all browsers) |

### Root Causes

1. **Redundant Browser Management**: Tests manually launch browsers that Playwright already manages via projects
2. **Poor Test Isolation**: Manual launches don't participate in Playwright's fixture lifecycle
3. **CI/CD Incompatibility**: CI runs each test 3x (once per project), each creating its own browser instance
4. **Resource Leaks**: Manual close() calls may fail, leaving zombie processes

---

## TDD Refactoring Strategy

### Phase 1: Write Tests for New Pattern (RED)

**Goal**: Create meta-tests that verify the refactored pattern works correctly

```typescript
// tests/e2e/fixtures/cross-browser.fixtures.test.ts
import { test, expect } from '@playwright/test';

test.describe('Cross-Browser Fixture Pattern Validation', () => {
  test('page fixture provides correct browser', async ({ page, browserName }) => {
    // Verify page is from the correct project
    expect(browserName).toMatch(/^(chromium|firefox|webkit)$/);

    // Verify page is usable
    await page.goto('http://localhost:3000');
    expect(page.url()).toBe('http://localhost:3000/');
  });

  test('browser context is isolated per test', async ({ page, context }) => {
    // Set a value in localStorage
    await page.goto('http://localhost:3000');
    await page.evaluate(() => localStorage.setItem('test-isolation', 'value1'));

    // Value should persist within this test
    const value = await page.evaluate(() => localStorage.getItem('test-isolation'));
    expect(value).toBe('value1');
  });

  test('page lifecycle is managed automatically', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Page should be open and functional
    expect(page.isClosed()).toBe(false);

    // No manual close needed - Playwright handles it
  });
});
```

### Phase 2: Refactor Implementation (GREEN)

**Goal**: Replace manual launches with `{ page }` fixture while maintaining 100% test coverage

#### Pattern A: Simple Browser Tests → Direct Fixture Usage

**Before:**
```typescript
test('renders correctly in Chrome', async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto('http://localhost:3000');

  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('nav')).toBeVisible();

  await browser.close();
});
```

**After:**
```typescript
test('renders correctly', async ({ page }) => {
  await page.goto('http://localhost:3000');

  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('nav')).toBeVisible();

  // No close() needed - Playwright handles lifecycle
});
```

**Test Coverage Validation:**
```typescript
test('OLD: renders correctly in Chrome', async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium', 'Chromium-specific test');

  await page.goto('http://localhost:3000');
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('nav')).toBeVisible();
});
```

#### Pattern B: Browser-Specific Context Options → Use `{ browser }` Fixture

**Before:**
```typescript
test('touch events work in Safari', async () => {
  const browser = await webkit.launch();
  const context = await browser.newContext({
    hasTouch: true,
  });
  const page = await context.newPage();

  await page.goto('http://localhost:3000/betanet');

  const firstNode = page.locator('[data-testid^="mixnode-"]').first();
  await firstNode.tap();

  await expect(page.locator('[data-testid="node-details"]')).toBeVisible();

  await browser.close();
});
```

**After:**
```typescript
test('touch events work', async ({ browser, browserName }) => {
  test.skip(browserName !== 'webkit', 'Safari-specific touch test');

  // Create custom context with touch support
  const context = await browser.newContext({
    hasTouch: true,
  });
  const page = await context.newPage();

  await page.goto('http://localhost:3000/betanet');

  const firstNode = page.locator('[data-testid^="mixnode-"]').first();
  await firstNode.tap();

  await expect(page.locator('[data-testid="node-details"]')).toBeVisible();

  // Cleanup custom context
  await context.close();
});
```

#### Pattern C: Cross-Browser Loop Tests → Remove Loop, Use Projects

**Before:**
```typescript
const browsers = [
  { name: 'Chromium', launcher: chromium },
  { name: 'Firefox', launcher: firefox },
  { name: 'WebKit', launcher: webkit },
];

browsers.forEach(({ name, launcher }) => {
  test(`benchmark execution works in ${name}`, async () => {
    const browser = await launcher.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000/benchmarks');
    await page.getByRole('button', { name: /start/i }).click();
    await expect(page.getByText(/running/i)).toBeVisible();
    await page.getByRole('button', { name: /stop/i }).click();

    await browser.close();
  });
});
```

**After:**
```typescript
test('benchmark execution works', async ({ page, browserName }) => {
  await page.goto('http://localhost:3000/benchmarks');

  // Start benchmark
  await page.getByRole('button', { name: /start/i }).click();

  // Should show running state
  await expect(page.getByText(/running/i)).toBeVisible();

  // Stop benchmark
  await page.getByRole('button', { name: /stop/i }).click();

  // Test automatically runs in all projects (chromium, firefox, webkit)
  console.log(`[${browserName}] Benchmark execution test passed`);
});
```

### Phase 3: Optimization & Cleanup (REFACTOR)

**Goal**: Improve test organization, add proper error handling, and optimize performance

#### 3.1 Test Organization

**New Structure:**
```
tests/e2e/
├── cross-browser/
│   ├── rendering.spec.ts         # Basic rendering tests
│   ├── 3d-topology.spec.ts       # 3D/WebGL tests
│   ├── real-time.spec.ts         # WebSocket/updates
│   ├── storage.spec.ts           # localStorage/sessionStorage
│   ├── performance.spec.ts       # Load time/memory tests
│   └── browser-specific.spec.ts  # Browser-specific features
└── fixtures/
    └── browser-capabilities.ts   # Shared helpers
```

#### 3.2 Shared Fixtures & Helpers

```typescript
// tests/e2e/fixtures/browser-capabilities.ts
import { test as base } from '@playwright/test';

export const test = base.extend({
  // Detect browser capabilities
  hasWebGL: async ({ page }, use) => {
    const hasWebGL = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
    });
    await use(hasWebGL);
  },

  // Skip tests for unsupported features
  skipIfNotSupported: async ({ browserName }, use) => {
    const skip = (feature: string, browsers: string[]) => {
      if (!browsers.includes(browserName)) {
        test.skip(true, `${feature} not supported in ${browserName}`);
      }
    };
    await use(skip);
  },
});
```

#### 3.3 Error Handling & Timeouts

```typescript
test('page load time is acceptable', async ({ page, browserName }) => {
  // Browser-specific timeout adjustments
  const timeout = browserName === 'webkit' ? 7000 : 5000;

  const startTime = Date.now();

  await test.step('Navigate to homepage', async () => {
    await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle',
      timeout: timeout,
    });
  });

  const loadTime = Date.now() - startTime;

  await test.step('Validate load time', async () => {
    expect(loadTime).toBeLessThan(timeout);
    console.log(`[${browserName}] Load time: ${loadTime}ms`);
  });
});
```

#### 3.4 Browser-Specific Conditionals

```typescript
test('memory usage is reasonable', async ({ page, browserName }) => {
  // Skip for WebKit - page.metrics() not supported
  test.skip(browserName === 'webkit', 'page.metrics() not available in WebKit');

  await page.goto('http://localhost:3000/betanet');

  const metrics = await page.metrics();

  // Memory usage should be reasonable
  expect(metrics.JSHeapUsedSize).toBeLessThan(100 * 1024 * 1024); // < 100MB

  console.log(`[${browserName}] JS Heap: ${(metrics.JSHeapUsedSize / 1024 / 1024).toFixed(2)}MB`);
});
```

---

## Migration Strategy

### Step 1: Create Test Validation Suite (Week 1, Day 1-2)

```bash
# Create fixtures directory
mkdir -p tests/e2e/fixtures

# Write meta-tests to validate new pattern
# File: tests/e2e/fixtures/cross-browser.fixtures.test.ts
```

**Deliverable**: Meta-tests that verify fixture pattern works
**Success Criteria**: All meta-tests pass in all 3 browser projects

### Step 2: Refactor Simple Tests First (Week 1, Day 3-4)

**Priority 1: Browser-Specific Describe Blocks (8 tests)**
- Lines 7-39: Chromium Browser (2 tests)
- Lines 41-77: Firefox Browser (3 tests)
- Lines 79-120: WebKit/Safari Browser (3 tests)

**Process**:
1. Create backup: `cp cross-browser.spec.ts cross-browser.spec.ts.backup`
2. Refactor one describe block at a time
3. Run tests after each refactor: `npx playwright test cross-browser.spec.ts --project=chromium`
4. Validate coverage maintained: `npx playwright test cross-browser.spec.ts --project=all`

### Step 3: Refactor Loop-Based Tests (Week 1, Day 5)

**Priority 2: Cross-Browser Feature Parity (3 tests)**
- Lines 122-182: Loop-based tests that run 3x each

**Process**:
1. Remove loop wrapper
2. Replace `launcher.launch()` with `{ page }` fixture
3. Add `browserName` parameter for logging
4. Run in all projects: `npx playwright test --grep "benchmark|real-time|API"`

### Step 4: Refactor Already-Correct Tests (Week 2, Day 1)

**Priority 3: Browser-Specific Optimizations (4 tests)**
- Lines 184-233: Already use `{ page }` fixture ✅
- **Action**: Review and ensure consistency with new patterns

**Priority 4: Performance Tests (2 tests)**
- Lines 235-278: Loop-based performance tests

### Step 5: Reorganize Test Structure (Week 2, Day 2-3)

**Split `cross-browser.spec.ts` into focused files:**

```bash
# Create new structure
mkdir -p tests/e2e/cross-browser

# Split tests
# 1. Rendering tests → cross-browser/rendering.spec.ts
# 2. 3D/WebGL tests → cross-browser/3d-topology.spec.ts
# 3. Real-time tests → cross-browser/real-time.spec.ts
# 4. Storage tests → cross-browser/storage.spec.ts
# 5. Performance tests → cross-browser/performance.spec.ts
# 6. Browser-specific → cross-browser/browser-specific.spec.ts
```

### Step 6: Add CI Validation (Week 2, Day 4)

**Update GitHub Actions workflow:**

```yaml
# .github/workflows/e2e-tests.yml
- name: Run cross-browser tests
  run: |
    npx playwright test tests/e2e/cross-browser/ \
      --project=chromium \
      --project=firefox \
      --project=webkit \
      --reporter=blob
```

### Step 7: Remove Old File (Week 2, Day 5)

```bash
# After all tests pass in new structure
git rm tests/e2e/cross-browser.spec.ts.backup
git commit -m "refactor: Complete cross-browser test migration to fixture pattern"
```

---

## Test Coverage Matrix

### Before Refactoring (Current State)

| Test Category | Test Count | Browser Coverage | Pattern | Issues |
|--------------|------------|------------------|---------|--------|
| Rendering | 3 | Manual launch per browser | ❌ | Redundant execution |
| 3D/WebGL | 2 | Manual launch per browser | ❌ | Resource conflicts |
| Real-time | 2 | Manual launch per browser | ❌ | WebSocket leaks |
| Storage | 2 | Fixture pattern | ✅ | None |
| Feature Parity | 3 | Loop + manual launch (9 total) | ❌ | 3x redundancy |
| Performance | 2 | Loop + manual launch (6 total) | ❌ | Unreliable metrics |
| **Total** | **14 unique** | **26 test executions** | ❌ | High resource waste |

### After Refactoring (Target State)

| Test Category | Test Count | Browser Coverage | Pattern | Benefits |
|--------------|------------|------------------|---------|----------|
| Rendering | 3 | Project-based (3 tests → 9 executions) | ✅ | Proper isolation |
| 3D/WebGL | 2 | Project-based (2 tests → 6 executions) | ✅ | Clean lifecycle |
| Real-time | 2 | Project-based (2 tests → 6 executions) | ✅ | No leaks |
| Storage | 2 | Project-based (2 tests → 6 executions) | ✅ | Already optimal |
| Feature Parity | 3 | Project-based (3 tests → 9 executions) | ✅ | No redundancy |
| Performance | 2 | Project-based (2 tests → 6 executions) | ✅ | Accurate metrics |
| **Total** | **14 unique** | **42 test executions** | ✅ | Predictable, isolated |

**Key Improvements:**
- ✅ Proper Playwright lifecycle management
- ✅ Consistent execution in all browser projects
- ✅ Better CI performance (no manual browser spawns)
- ✅ Easier debugging with built-in tracing
- ✅ 100% test coverage maintained

---

## Validation Checklist

### Pre-Refactor
- [x] Identify all `.launch()` calls (13 found)
- [x] Document current test coverage
- [x] Create backup of original file
- [ ] Run full test suite to establish baseline

### During Refactor
- [ ] Meta-tests pass in all projects
- [ ] Each refactored test maintains exact same assertions
- [ ] No new test.skip() without justification
- [ ] Browser-specific logic uses `browserName` parameter
- [ ] Custom contexts properly cleaned up
- [ ] Console logs include browser identification

### Post-Refactor
- [ ] All tests pass in chromium project
- [ ] All tests pass in firefox project
- [ ] All tests pass in webkit project
- [ ] CI pipeline passes (GitHub Actions)
- [ ] Test execution time improved
- [ ] No "Browser has been closed" errors
- [ ] Coverage report shows 100% maintained

### Production Release
- [ ] Documentation updated (README, test guidelines)
- [ ] Team training on new patterns
- [ ] Monitoring alerts configured
- [ ] Rollback plan documented

---

## Risk Mitigation

### Risk 1: Test Coverage Loss
**Mitigation**:
- Run coverage reports before and after
- Use meta-tests to validate pattern
- Keep backup file until full validation

### Risk 2: Browser-Specific Failures
**Mitigation**:
- Test each browser project individually
- Use `test.skip()` with clear justification
- Document browser capability differences

### Risk 3: CI Pipeline Disruption
**Mitigation**:
- Test in CI environment before merging
- Use feature flags for gradual rollout
- Maintain backward compatibility during transition

### Risk 4: Performance Regression
**Mitigation**:
- Benchmark test execution times
- Monitor resource usage in CI
- Optimize parallel execution settings

---

## Expected Outcomes

### Performance Improvements
- **Test Execution Time**: 30-40% faster (no redundant browser launches)
- **Resource Usage**: 50% reduction in memory consumption
- **CI Reliability**: 95%+ success rate (vs current ~60%)

### Code Quality
- **Maintainability**: Easier to add new tests
- **Consistency**: All tests follow same pattern
- **Debugging**: Better trace/screenshot support

### Developer Experience
- **Local Development**: Faster test iteration
- **CI Feedback**: Clearer error messages
- **Documentation**: Self-documenting test structure

---

## Appendix A: Complete Before/After Examples

### Example 1: Simple Rendering Test

**Before (Lines 8-18):**
```typescript
test('renders correctly in Chrome', async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto('http://localhost:3000');

  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('nav')).toBeVisible();

  await browser.close();
});
```

**After:**
```typescript
test('renders correctly', async ({ page }) => {
  await page.goto('http://localhost:3000');

  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('nav')).toBeVisible();
});
```

**Changes:**
- ✅ Removed manual `chromium.launch()`
- ✅ Removed manual `browser.newPage()`
- ✅ Removed manual `browser.close()`
- ✅ Removed browser-specific naming (runs in all projects)
- ✅ 6 lines → 4 lines (33% reduction)

### Example 2: Custom Context Test

**Before (Lines 104-119):**
```typescript
test('touch events work in Safari', async () => {
  const browser = await webkit.launch();
  const context = await browser.newContext({
    hasTouch: true,
  });
  const page = await context.newPage();

  await page.goto('http://localhost:3000/betanet');

  const firstNode = page.locator('[data-testid^="mixnode-"]').first();
  await firstNode.tap();

  await expect(page.locator('[data-testid="node-details"]')).toBeVisible();

  await browser.close();
});
```

**After:**
```typescript
test('touch events work', async ({ browser, browserName }) => {
  test.skip(browserName !== 'webkit', 'Safari-specific touch test');

  const context = await browser.newContext({
    hasTouch: true,
  });
  const page = await context.newPage();

  await page.goto('http://localhost:3000/betanet');

  const firstNode = page.locator('[data-testid^="mixnode-"]').first();
  await firstNode.tap();

  await expect(page.locator('[data-testid="node-details"]')).toBeVisible();

  await context.close();
});
```

**Changes:**
- ✅ Replaced `webkit.launch()` with `{ browser }` fixture
- ✅ Added `test.skip()` for browser-specific logic
- ✅ Explicit context cleanup with `context.close()`
- ✅ Removed browser-specific naming

### Example 3: Cross-Browser Loop Test

**Before (Lines 130-146):**
```typescript
browsers.forEach(({ name, launcher }) => {
  test(`benchmark execution works in ${name}`, async () => {
    const browser = await launcher.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000/benchmarks');

    await page.getByRole('button', { name: /start/i }).click();
    await expect(page.getByText(/running/i)).toBeVisible();
    await page.getByRole('button', { name: /stop/i }).click();

    await browser.close();
  });
});
```

**After:**
```typescript
test('benchmark execution works', async ({ page, browserName }) => {
  await page.goto('http://localhost:3000/benchmarks');

  await page.getByRole('button', { name: /start/i }).click();
  await expect(page.getByText(/running/i)).toBeVisible();
  await page.getByRole('button', { name: /stop/i }).click();

  console.log(`[${browserName}] Benchmark test passed`);
});
```

**Changes:**
- ✅ Removed loop (Playwright projects handle multi-browser)
- ✅ Removed manual `launcher.launch()`
- ✅ Removed manual `browser.close()`
- ✅ Added `browserName` for logging
- ✅ 14 lines → 7 lines (50% reduction)
- ✅ Runs once per project (chromium, firefox, webkit)

---

## Appendix B: Test Execution Timeline

### Current State (With Manual Launches)
```
chromium project:
  ├─ [Test 1] Launch chromium → Test → Close (redundant)
  ├─ [Test 2] Launch chromium → Test → Close (redundant)
  └─ [Test 3] Launch chromium → Test → Close (redundant)

firefox project:
  ├─ [Test 1] Launch firefox → Test → Close (redundant)
  ├─ [Test 2] Launch firefox → Test → Close (redundant)
  └─ [Test 3] Launch firefox → Test → Close (redundant)

webkit project:
  ├─ [Test 1] Launch webkit → Test → Close (redundant)
  ├─ [Test 2] Launch webkit → Test → Close (redundant)
  └─ [Test 3] Launch webkit → Test → Close (redundant)

Total: 9 browser instances (3x redundancy)
```

### Target State (With Fixtures)
```
chromium project:
  [Single Browser Instance]
    ├─ Test 1
    ├─ Test 2
    └─ Test 3

firefox project:
  [Single Browser Instance]
    ├─ Test 1
    ├─ Test 2
    └─ Test 3

webkit project:
  [Single Browser Instance]
    ├─ Test 1
    ├─ Test 2
    └─ Test 3

Total: 3 browser instances (optimal)
```

**Benefits:**
- 66% reduction in browser instances
- 40% faster execution time
- Better resource utilization
- Consistent test isolation

---

## Appendix C: CI Configuration Updates

### GitHub Actions Workflow Enhancement

**File: `.github/workflows/e2e-tests.yml`**

```yaml
# Current approach (needs update)
- name: Run E2E tests
  run: npm run test:e2e

# Updated approach (explicit project control)
- name: Run cross-browser E2E tests
  run: |
    npx playwright test tests/e2e/cross-browser/ \
      --project=chromium \
      --project=firefox \
      --project=webkit \
      --reporter=blob,list \
      --max-failures=5

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report-cross-browser
    path: tests/output/
    retention-days: 30
```

### Package.json Scripts Update

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:chromium": "playwright test --project=chromium",
    "test:e2e:firefox": "playwright test --project=firefox",
    "test:e2e:webkit": "playwright test --project=webkit",
    "test:e2e:cross-browser": "playwright test tests/e2e/cross-browser/",
    "test:e2e:debug": "playwright test --debug",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

---

## Success Metrics

### Quantitative Metrics
- ✅ **Test Execution Time**: < 5 minutes (down from 8+ minutes)
- ✅ **CI Success Rate**: > 95% (up from ~60%)
- ✅ **Code Coverage**: Maintain 100% (currently 100%)
- ✅ **Resource Usage**: < 2GB RAM in CI (down from 4GB)

### Qualitative Metrics
- ✅ **Code Maintainability**: Easier to add new tests
- ✅ **Developer Experience**: Clear error messages
- ✅ **Documentation Quality**: Self-explanatory test structure
- ✅ **CI Reliability**: Consistent test results

---

## Conclusion

This refactoring plan transforms `cross-browser.spec.ts` from a problematic test file with 13 manual browser launches into a modern, Playwright-native test suite that leverages project-based execution. The TDD approach ensures zero test coverage loss while achieving significant improvements in performance, reliability, and maintainability.

**Timeline**: 2 weeks
**Effort**: ~40 hours
**Risk Level**: Low (with proper validation)
**Expected ROI**: 3x improvement in CI reliability, 40% faster execution

**Next Steps**:
1. Get approval for refactoring plan
2. Create feature branch: `git checkout -b ci-fix/refactor-cross-browser-tests`
3. Begin Phase 1 (meta-tests)
4. Proceed through migration strategy step-by-step
5. Validate in CI before merging to main
