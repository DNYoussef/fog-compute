import { defineConfig } from '@playwright/test';

/**
 * Playwright merge configuration for cross-OS report merging
 *
 * This config resolves path differences between Windows and Linux CI runners
 * by explicitly specifying testDir, allowing reports from both OS to be merged.
 *
 * Without this, merge fails with:
 * "Blob reports being merged were recorded with different test directories"
 * - Windows: D:\a\fog-compute\fog-compute\tests\e2e
 * - Linux: /home/runner/work/fog-compute/fog-compute/tests/e2e
 */
export default defineConfig({
  testDir: './tests/e2e',
});
