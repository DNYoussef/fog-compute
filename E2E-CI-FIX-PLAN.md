# E2E CI/CD Fix Plan

## Current Issues Identified

### Issue 1: Missing npm dependency `axe-playwright` (CRITICAL)
**Error**: `Cannot find module 'axe-playwright'`
**Files affected**:
- `tests/e2e/test_protected_routes.spec.ts:6`
- `tests/e2e/test_quality_panel_flow.spec.ts:17`
- `tests/e2e/test_registration_flow.spec.ts:7`

**Fix**: Add `axe-playwright` to root `package.json` devDependencies

### Issue 2: Redis not provisioned (LOW - graceful degradation works)
**Error**: `Error 111 connecting to localhost:6379`
**Impact**: Caching unavailable, but backend continues running

**Fix Options**:
- A) Add Redis service to CI (recommended for production parity)
- B) Keep as-is (graceful degradation sufficient for E2E tests)

### Issue 3: Report merge fails across OS (Windows vs Linux paths)
**Error**: Different test directories found
- `D:\a\fog-compute\fog-compute\tests\e2e`
- `/home/runner/work/fog-compute/fog-compute/tests/e2e`

**Fix**: Add merge config with explicit testDir

### Issue 4: PostgreSQL is already provisioned
**Status**: WORKING - using `ikalnytskyi/action-setup-postgres@v5`

---

## Implementation Plan

### Phase 1: Fix Missing Dependencies (IMMEDIATE)

```bash
# Add axe-playwright to root package.json
npm install -D axe-playwright
```

Files to modify:
- `package.json` - add devDependency

### Phase 2: Add Redis Service (OPTIONAL but recommended)

Modify `.github/workflows/e2e-tests.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### Phase 3: Fix Cross-OS Report Merging

Create `playwright.merge.config.ts`:
```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
});
```

Update `.github/workflows/e2e-tests.yml`:
```yaml
- name: Merge reports
  run: |
    npx playwright merge-reports -c playwright.merge.config.ts --reporter html ./all-blob-reports
```

---

## Execution Order

1. **Step 1**: Install `axe-playwright` dependency
2. **Step 2**: Create `playwright.merge.config.ts`
3. **Step 3**: Update `e2e-tests.yml` for merge config
4. **Step 4**: (Optional) Add Redis service to CI
5. **Step 5**: Commit and push
6. **Step 6**: Verify CI passes

---

## Files to Modify

| File | Change |
|------|--------|
| `package.json` | Add `axe-playwright` devDependency |
| `playwright.merge.config.ts` | Create new file for report merging |
| `.github/workflows/e2e-tests.yml` | Add merge config, optionally add Redis |

---

## Expected Results After Fix

| Workflow | Expected Status |
|----------|-----------------|
| Node.js Tests | PASS (already passing) |
| Rust Tests | PASS (already passing) |
| E2E Tests (Ubuntu) | PASS |
| E2E Tests (Windows) | PASS |
| Mobile Tests | PASS |
| Cross-browser Tests | PASS |
| Report Merge | PASS |
