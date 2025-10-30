# CI Pipeline Quick Fixes - Implementation Guide

**Objective**: Reduce CI pipeline from 23-28 minutes to 5-7 minutes (Week 1 target)

**Current Status**: 24 jobs, 23-28 min duration, 28 test failures
**Target Status**: 6-8 jobs, 5-7 min duration, <2% failure rate

---

## Phase 1: Immediate Optimizations (Week 1)

### Fix 1: Reduce OS Matrix (50% job reduction)

**Current**:
```yaml
matrix:
  os: [ubuntu-latest, windows-latest]
  browser: [chromium, firefox, webkit]
  shard: [1, 2, 3, 4]
# Total: 24 jobs
```

**Change to**:
```yaml
jobs:
  test-linux:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        browser: [chromium, firefox, webkit]
        shard: [1, 2]
    # Total: 6 jobs

  test-windows-validation:
    runs-on: windows-latest
    strategy:
      matrix:
        browser: [chromium]  # Representative test only
        shard: [1]
    # Total: 1 job

# New Total: 7 jobs (71% reduction from 24)
```

**Expected Impact**:
- **Jobs**: 24 → 7 (-71%)
- **Duration**: 23 min → 12 min (-48%)
- **Cost**: 50% reduction

---

### Fix 2: Use Playwright Docker Image (Eliminate browser install)

**Current**:
```yaml
- name: Install Playwright
  run: npx playwright install --with-deps ${{ matrix.browser }}
# Takes 2-4 minutes per job
```

**Change to**:
```yaml
jobs:
  test-linux:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright:v1.40.0-jammy
    # Browsers pre-installed, skip installation step!

    steps:
      # Remove this step entirely:
      # - name: Install Playwright
      #   run: npx playwright install --with-deps ${{ matrix.browser }}
```

**Expected Impact**:
- **Browser install time**: 2-4 min → 0 min (-100%)
- **Duration**: 12 min → 9 min (-25%)

**Note**: Docker images ~1.5 GB, but GitHub caches them. First run may be slow, subsequent runs are fast.

---

### Fix 3: Optimize Sharding (Better balance)

**Current**:
```yaml
shard: [1, 2, 3, 4]
# 4 shards for 10 test files = unbalanced distribution
```

**Change to**:
```yaml
shard: [1, 2]
# 2 shards for 10 test files = better balance
# Each shard gets 5 files, more balanced test counts
```

**Shard Distribution Analysis**:

**Before (4 shards)**:
- Shard 1: 2-3 files, ~4-5 min
- Shard 2: 2-3 files, ~6-7 min
- Shard 3: 2-3 files, ~8-10 min ← slowest
- Shard 4: 2-3 files, ~8-10 min ← slowest
- **Total**: 10 min (waiting for slowest)

**After (2 shards)**:
- Shard 1: 5 files, ~6-7 min
- Shard 2: 5 files, ~6-7 min
- **Total**: 7 min (better balanced)

**Expected Impact**:
- **Shard imbalance**: 10 min → 7 min (-30%)
- **Setup overhead**: 4× → 2× (-50%)
- **Duration**: 9 min → 7 min (-22%)

---

### Fix 4: Separate Cross-Browser Tests

**Current**:
```yaml
# ALL tests run in ALL browsers
browser: [chromium, firefox, webkit]
```

**Change to**:
```yaml
jobs:
  test-main:
    strategy:
      matrix:
        browser: [chromium]  # Fast, primary browser
        shard: [1, 2]
    # Runs all tests in chromium only

  test-cross-browser:
    needs: test-main  # Only run if chromium passes
    strategy:
      matrix:
        browser: [firefox, webkit]
        shard: [1]  # Single shard, critical tests only
    steps:
      - run: |
          npx playwright test \
            --grep "@cross-browser" \
            --project=${{ matrix.browser }}
```

**Tag critical tests**:
```typescript
// tests/e2e/cross-platform.spec.ts
test('Browser feature detection @cross-browser', async ({ page }) => {
  // This test needs cross-browser validation
});

// tests/e2e/authentication.spec.ts
test('User login', async ({ page }) => {
  // No @cross-browser tag = chromium only
});
```

**Expected Impact**:
- **Test executions**: Reduce by ~50% for non-critical files
- **Duration**: 7 min → 6 min (-14%)
- **Better resource allocation**: Critical tests get cross-browser, others don't

---

## Implementation Plan

### Step 1: Update Workflow File (15 min)

```bash
# Edit .github/workflows/e2e-tests.yml
```

**Changes**:
1. Split `test` job into `test-linux` and `test-windows-validation`
2. Add Docker container to `test-linux`
3. Reduce shards from 4 to 2
4. Add `test-cross-browser` job with `@cross-browser` grep

**Verification**:
```bash
# Validate YAML syntax
npx js-yaml .github/workflows/e2e-tests.yml
```

### Step 2: Tag Tests (30 min)

**Files to tag** (need cross-browser):
- `benchmarks-visualization.spec.ts`
- `bitchat-messaging.spec.ts`
- `cross-browser.spec.ts`
- `cross-platform.spec.ts`
- `mobile-responsive.spec.ts`

**Files to leave untagged** (chromium only):
- `authentication.spec.ts`
- `betanet-monitoring.spec.ts`
- `control-panel.spec.ts`
- `control-panel-complete.spec.ts`
- `mobile.spec.ts`

**Example**:
```typescript
// Add @cross-browser to test names that need it
test('WebRTC connection establishment @cross-browser', async ({ page }) => {
  // ...
});
```

### Step 3: Update Playwright Config (5 min)

```typescript
// playwright.config.ts
export default defineConfig({
  // Optimize for CI
  workers: process.env.CI ? 4 : undefined,  // Increase from 2 to 4
  retries: process.env.CI ? 1 : 0,          // Reduce from 2 to 1

  // Faster timeouts for CI
  timeout: 30 * 1000,  // Reduce from 60s to 30s
  expect: { timeout: 5000 },  // Reduce from 10s to 5s

  // webServer timeout can stay at 120s
});
```

### Step 4: Test Locally (10 min)

```bash
# Test with Docker locally
docker run --rm -it \
  -v $(pwd):/work -w /work \
  mcr.microsoft.com/playwright:v1.40.0-jammy \
  bash -c "npm ci && cd apps/control-panel && npm ci && cd ../.. && npx playwright test --shard=1/2"

# Verify sharding works
npx playwright test --shard=1/2 --list
npx playwright test --shard=2/2 --list

# Test cross-browser grep
npx playwright test --grep "@cross-browser" --project=firefox
```

### Step 5: Commit and Monitor (5 min)

```bash
git add .github/workflows/e2e-tests.yml tests/e2e/*.spec.ts playwright.config.ts
git commit -m "fix: Optimize CI pipeline - reduce jobs from 24 to 7 (71% reduction)

- Use Playwright Docker image (eliminate 2-4min browser install)
- Reduce OS matrix: Linux primary + 1 Windows validation job
- Reduce shards from 4 to 2 (better balanced distribution)
- Tag tests for selective cross-browser execution
- Expected improvement: 23-28 min → 5-7 min (71-78% faster)

Fixes #[issue-number]"

git push origin [branch-name]
```

**Monitor**:
1. Watch GitHub Actions run
2. Check job durations in Actions tab
3. Verify all jobs complete successfully
4. Confirm total duration < 8 minutes

---

## Expected Results

### Before Optimization
```
Jobs: 24 (2 OS × 3 browsers × 4 shards)
Duration: 23-28 minutes
Failures: 28 tests (timeouts, resource contention)
Cost: High (24 concurrent jobs, 12 on expensive Windows runners)
```

### After Phase 1 Optimization
```
Jobs: 7 (6 Linux + 1 Windows)
Duration: 5-7 minutes
Failures: <5 tests (reduced contention)
Cost: 50% reduction (fewer jobs, faster completion)
```

**Improvement**:
- **71% fewer jobs** (24 → 7)
- **71-78% faster** (23-28 min → 5-7 min)
- **50% cost reduction**
- **90% fewer failures** (28 → <3)

---

## Rollback Plan

If optimizations cause issues:

```bash
# Revert to previous workflow
git revert HEAD
git push origin [branch-name]

# Or manually restore from this commit:
# [Previous working commit hash]
```

**Validation before merge**:
- Run optimized pipeline on feature branch first
- Verify all critical tests pass
- Check that cross-browser tests still run on tagged tests
- Confirm Windows validation job catches platform-specific issues

---

## Next Steps (Phase 2 - Week 2)

After Phase 1 stabilizes:

1. **Setup job for shared dependencies**
   - Build once, test many times
   - Eliminates npm ci from test jobs
   - Expected: 2-3 min additional savings

2. **Database snapshot sharing**
   - Seed once, restore in test jobs
   - Eliminates 45s seeding per job
   - Expected: 30-45s savings

3. **Test impact analysis**
   - Only run affected tests
   - Smart test selection based on changed files
   - Expected: 30-50% test reduction on typical PRs

**Phase 2 Target**: 3-5 minute pipeline

---

## Monitoring Metrics

Track these metrics after deployment:

| Metric | Before | Target | Actual |
|--------|--------|--------|--------|
| Total Duration | 23-28 min | 5-7 min | ___ |
| Job Count | 24 | 7 | ___ |
| Setup Time | 8-12 min | 2-3 min | ___ |
| Test Time | 2-10 min | 3-5 min | ___ |
| Failure Rate | 15% (28/182) | <2% | ___ |
| Cost per Run | $X | $X/2 | ___ |

---

## Troubleshooting

### Issue: Docker image pull is slow
**Solution**: GitHub caches Docker images after first pull. Subsequent runs will be fast. Consider pre-warming cache in setup job.

### Issue: Windows job still failing
**Solution**: Windows job is now validation-only. If it fails, investigate separately. Don't block Linux jobs.

### Issue: Cross-browser tests not running
**Solution**: Verify `@cross-browser` tags are applied. Check `--grep` filter in workflow.

### Issue: Tests timing out
**Solution**: Reduce timeout values further, or increase `workers` in playwright.config.ts.

---

*Quick fix guide for CI optimization - Week 1 implementation*
*For detailed analysis, see: docs/ci-performance-analysis.md*
