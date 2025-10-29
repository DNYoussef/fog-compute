import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E testing
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './tests/e2e',

  // Maximum time one test can run
  timeout: 60 * 1000,

  expect: {
    timeout: 10000,
  },

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Moderate parallelism on CI for better performance
  workers: process.env.CI ? 2 : undefined,

  // Reporter to use - blob reporter for sharded test merging in CI
  reporter: process.env.CI ? [
    ['blob'],  // Blob reporter for sharded test merging in CI
    ['list'],  // Console output
  ] : [
    ['html', { outputFolder: 'tests/output/playwright-report' }],
    ['json', { outputFile: 'tests/output/playwright-results.json' }],
    ['junit', { outputFile: 'tests/output/playwright-results.xml' }],
    ['list'],
  ],

  // Shared settings for all projects
  use: {
    // Base URL for navigation
    baseURL: 'http://localhost:3000',

    // Enhanced trace collection
    trace: {
      mode: 'on-first-retry',
      screenshots: true,
      snapshots: true,
      sources: true,
    },

    // Screenshot configuration
    screenshot: {
      mode: 'only-on-failure',
      fullPage: true,
    },

    // Video recording with custom size
    video: {
      mode: 'retain-on-failure',
      size: { width: 1920, height: 1080 }
    },

    // Network HAR recording
    contextOptions: {
      recordHar: process.env.RECORD_HAR ? {
        path: 'test-results/network.har',
        mode: 'minimal'
      } : undefined,
    },

    // Advanced timeouts
    actionTimeout: 15 * 1000,
    navigationTimeout: 45 * 1000,

    // Browser launch options
    launchOptions: {
      slowMo: process.env.SLOWMO ? parseInt(process.env.SLOWMO) : 0,
    },

    // Ignore HTTPS errors in development
    ignoreHTTPSErrors: true,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    // Mobile browsers
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },

    // Tablet browsers
    {
      name: 'iPad',
      use: { ...devices['iPad Pro'] },
    },

    // Desktop with different viewport sizes
    {
      name: 'Desktop Large',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 },
      },
    },
    {
      name: 'Desktop Small',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1366, height: 768 },
      },
    },
  ],

  // Run local dev server before starting tests
  // CRITICAL: Start both backend AND frontend for E2E tests
  // Playwright automatically manages server lifecycle (start before tests, stop after)
  webServer: [
    {
      // FIXED: Use cwd instead of shell "cd" command to avoid platform-specific issues
      // Windows cmd.exe and Unix bash handle "cd && command" differently
      command: 'python -m uvicorn server.main:app --port 8000',
      cwd: 'backend',  // Playwright's native cwd support (cross-platform)
      url: 'http://localhost:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,  // Increased from 60s for database initialization
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        // FIXED: Explicit environment object instead of spread operator
        // Windows subprocess may not inherit process.env reliably via spread
        // Only pass essential variables explicitly to ensure propagation
        DATABASE_URL: process.env.DATABASE_URL || (() => {
          if (process.env.CI === 'true') {
            throw new Error('CRITICAL: DATABASE_URL not set in CI environment. Check GitHub Actions workflow export to $GITHUB_ENV');
          }
          // Local dev fallback - use same default as backend config.py
          return 'postgresql+asyncpg://postgres:postgres@localhost:5432/fog_compute_test';
        })(),
        PATH: process.env.PATH || '',
        PYTHONPATH: process.env.PYTHONPATH || '',
        // Pass CI flag to backend for validation
        CI: process.env.CI || '',
      },
    },
    {
      // Frontend server - use cwd for consistency
      command: 'npm run dev',
      cwd: 'apps/control-panel',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],

  // Output folder for test artifacts
  outputDir: 'tests/output/playwright-artifacts',
});
