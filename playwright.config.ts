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

  // CI optimization: Single worker for stability, full parallelism locally
  workers: process.env.CI ? 1 : undefined,

  // Reporter to use - blob reporter for sharded test merging in CI
  reporter: process.env.CI ? 'blob' : [
    ['html', { outputFolder: 'tests/output/playwright-report' }],
    ['json', { outputFile: 'tests/output/playwright-results.json' }],
    ['junit', { outputFile: 'tests/output/playwright-results.xml' }],
    ['list'],
  ],

  // Shared settings for all projects
  use: {
    // Base URL for navigation
    baseURL: 'http://localhost:3000',

    // Trace collection - simplified for performance
    trace: 'on-first-retry',

    // Screenshot configuration
    screenshot: 'only-on-failure',

    // Video recording - disabled by default for performance
    video: process.env.RECORD_VIDEO ? 'retain-on-failure' : 'off',


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
  // CI and Local: Run all browsers to catch browser-specific bugs
  projects: process.env.CI ? [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // CI-specific optimizations
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1280, height: 720 },
      },
    },
    // Mobile projects for mobile-tests job
    {
      name: 'Pixel 5',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'iPhone 12',
      use: { ...devices['iPhone 12'] },
    },
    {
      name: 'iPad Pro',
      use: { ...devices['iPad Pro'] },
    },
  ] : [
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
      reuseExistingServer: false,  // Always start fresh servers for each test run to avoid port conflicts
      timeout: 120 * 1000,  // Increased from 60s for database initialization
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        // Explicit environment variables for cross-platform compatibility
        DATABASE_URL: process.env.DATABASE_URL ||
          'postgresql+asyncpg://postgres:postgres@localhost:5432/fog_compute_test',
        PATH: process.env.PATH || '',
        PYTHONPATH: process.env.PYTHONPATH || '',
        CI: process.env.CI || '',
        SKIP_EXTERNAL_SERVICES: process.env.SKIP_EXTERNAL_SERVICES || '',
        SERVICE_INIT_TIMEOUT: process.env.SERVICE_INIT_TIMEOUT || '',
        P2P_TIMEOUT: process.env.P2P_TIMEOUT || '',
        BETANET_URL: process.env.BETANET_URL || '',
        // Additional backend configuration
        ENVIRONMENT: process.env.CI ? 'test' : 'development',
        LOG_LEVEL: process.env.CI ? 'WARNING' : 'INFO',
      },
    },
    {
      // Frontend server - use cwd for consistency
      command: 'npm run dev',
      cwd: 'apps/control-panel',
      url: 'http://localhost:3000',
      reuseExistingServer: false,  // Always start fresh servers for each test run
      timeout: 120 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],

  // Output folder for test artifacts
  outputDir: 'tests/output/playwright-artifacts',
});
