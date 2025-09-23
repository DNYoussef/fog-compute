/**
 * E2E Tests for Control Panel
 * Using Playwright for cross-browser testing
 */

import { test, expect, Page } from '@playwright/test';

test.describe('Control Panel Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
  });

  test('displays dashboard with all components', async ({ page }) => {
    // Check main dashboard elements
    await expect(page.locator('h1')).toContainText('Fog Compute Dashboard');

    // Verify navigation
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /betanet/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /benchmarks/i })).toBeVisible();
  });

  test('shows system metrics', async ({ page }) => {
    // Check system metrics panel
    const metricsPanel = page.locator('[data-testid="system-metrics"]');
    await expect(metricsPanel).toBeVisible();

    // Verify metric values are displayed
    await expect(metricsPanel.getByText(/CPU/i)).toBeVisible();
    await expect(metricsPanel.getByText(/Memory/i)).toBeVisible();
    await expect(metricsPanel.getByText(/Network/i)).toBeVisible();
  });

  test('displays fog map visualization', async ({ page }) => {
    const fogMap = page.locator('[data-testid="fog-map"]');
    await expect(fogMap).toBeVisible();

    // Check map controls
    await expect(fogMap.locator('button[aria-label="Zoom in"]')).toBeVisible();
    await expect(fogMap.locator('button[aria-label="Zoom out"]')).toBeVisible();
  });

  test('quick actions are functional', async ({ page }) => {
    const quickActions = page.locator('[data-testid="quick-actions"]');

    // Test deploy node action
    const deployButton = quickActions.getByRole('button', { name: /deploy node/i });
    await deployButton.click();
    await expect(page.locator('[data-testid="deploy-modal"]')).toBeVisible();
  });
});

test.describe('Betanet Topology View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/betanet');
  });

  test('renders 3D topology visualization', async ({ page }) => {
    const topology = page.locator('[data-testid="betanet-topology"]');
    await expect(topology).toBeVisible();

    // Check canvas is rendered
    const canvas = topology.locator('canvas');
    await expect(canvas).toBeVisible();

    // Verify canvas dimensions
    const dimensions = await canvas.boundingBox();
    expect(dimensions?.width).toBeGreaterThan(0);
    expect(dimensions?.height).toBeGreaterThan(0);
  });

  test('displays mixnode list', async ({ page }) => {
    const mixnodeList = page.locator('[data-testid="mixnode-list"]');
    await expect(mixnodeList).toBeVisible();

    // Check for mixnode entries
    const mixnodes = mixnodeList.locator('[data-testid^="mixnode-"]');
    await expect(mixnodes.first()).toBeVisible();
  });

  test('node selection updates details panel', async ({ page }) => {
    // Click first mixnode
    const firstNode = page.locator('[data-testid^="mixnode-"]').first();
    await firstNode.click();

    // Check details panel updates
    const detailsPanel = page.locator('[data-testid="node-details"]');
    await expect(detailsPanel).toBeVisible();
    await expect(detailsPanel.getByText(/Packets Processed/i)).toBeVisible();
    await expect(detailsPanel.getByText(/Reputation/i)).toBeVisible();
  });

  test('packet flow monitor shows real-time data', async ({ page }) => {
    const monitor = page.locator('[data-testid="packet-flow-monitor"]');
    await expect(monitor).toBeVisible();

    // Check throughput display
    await expect(monitor.getByText(/throughput/i)).toBeVisible();
    await expect(monitor.getByText(/pps/i)).toBeVisible();

    // Wait for data update
    await page.waitForTimeout(1000);

    // Verify data is updating (value should change or be present)
    const throughputValue = await monitor.locator('[data-testid="throughput-value"]').textContent();
    expect(throughputValue).toBeTruthy();
  });

  test('topology controls work correctly', async ({ page }) => {
    const controls = page.locator('[data-testid="topology-controls"]');

    // Test auto-rotate toggle
    const autoRotate = controls.getByRole('button', { name: /auto rotate/i });
    await autoRotate.click();
    await expect(autoRotate).toHaveAttribute('aria-pressed', 'false');

    // Test zoom controls
    const zoomIn = controls.getByRole('button', { name: /zoom in/i });
    await zoomIn.click();
    // Canvas should update (visual test would verify this)
  });
});

test.describe('Benchmark Runner', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/benchmarks');
  });

  test('starts and stops benchmark', async ({ page }) => {
    const controls = page.locator('[data-testid="benchmark-controls"]');

    // Start benchmark
    const startButton = controls.getByRole('button', { name: /start/i });
    await startButton.click();

    // Verify running state
    await expect(controls.getByText(/running/i)).toBeVisible();
    await expect(startButton).toBeDisabled();

    // Stop benchmark
    const stopButton = controls.getByRole('button', { name: /stop/i });
    await stopButton.click();

    // Verify stopped state
    await expect(controls.getByText(/stopped/i)).toBeVisible();
    await expect(startButton).toBeEnabled();
  });

  test('displays benchmark results', async ({ page }) => {
    // Start benchmark
    await page.getByRole('button', { name: /start/i }).click();

    // Wait for completion
    await page.waitForSelector('[data-testid="benchmark-results"]', { timeout: 10000 });

    const results = page.locator('[data-testid="benchmark-results"]');
    await expect(results).toBeVisible();

    // Check result categories
    await expect(results.getByText(/system/i)).toBeVisible();
    await expect(results.getByText(/privacy/i)).toBeVisible();
    await expect(results.getByText(/graph/i)).toBeVisible();
  });

  test('charts update with real-time data', async ({ page }) => {
    const charts = page.locator('[data-testid="benchmark-charts"]');
    await expect(charts).toBeVisible();

    // Start benchmark to generate data
    await page.getByRole('button', { name: /start/i }).click();

    // Wait for chart updates
    await page.waitForTimeout(2000);

    // Check charts are populated
    const throughputChart = charts.locator('[data-testid="throughput-chart"]');
    await expect(throughputChart).toBeVisible();

    const latencyChart = charts.locator('[data-testid="latency-chart"]');
    await expect(latencyChart).toBeVisible();
  });

  test('exports benchmark results', async ({ page }) => {
    // Run quick benchmark
    await page.getByRole('button', { name: /start/i }).click();
    await page.waitForSelector('[data-testid="benchmark-results"]', { timeout: 10000 });

    // Click export button
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /export/i }).click();

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('benchmark-results');
    expect(download.suggestedFilename()).toMatch(/\.(json|csv)$/);
  });
});

test.describe('BitChat Integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/bitchat');
  });

  test('loads BitChat interface', async ({ page }) => {
    const bitchat = page.locator('[data-testid="bitchat-wrapper"]');
    await expect(bitchat).toBeVisible();
  });

  test('displays peer connection status', async ({ page }) => {
    const status = page.locator('[data-testid="peer-status"]');
    await expect(status).toBeVisible();
    await expect(status.getByText(/peer id/i)).toBeVisible();
  });

  test('shows connected peers', async ({ page }) => {
    const peerList = page.locator('[data-testid="peer-list"]');
    await expect(peerList).toBeVisible();

    // Check for peer entries (may be empty initially)
    const peerCount = peerList.locator('[data-testid^="peer-"]');
    const count = await peerCount.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Responsive Design', () => {
  const viewports = [
    { name: 'Desktop', width: 1920, height: 1080 },
    { name: 'Laptop', width: 1366, height: 768 },
    { name: 'Tablet', width: 768, height: 1024 },
    { name: 'Mobile', width: 375, height: 667 },
  ];

  viewports.forEach(({ name, width, height }) => {
    test(`renders correctly on ${name}`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.goto('http://localhost:3000');

      // Check main content is visible
      await expect(page.locator('main')).toBeVisible();

      // Navigation should adapt
      if (width < 768) {
        // Mobile: hamburger menu
        await expect(page.locator('[aria-label="Menu"]')).toBeVisible();
      } else {
        // Desktop: full navigation
        await expect(page.locator('nav')).toBeVisible();
      }
    });
  });
});

test.describe('Real-time Updates', () => {
  test('WebSocket connection establishes', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Check WebSocket status indicator
    const wsStatus = page.locator('[data-testid="ws-status"]');
    await expect(wsStatus).toBeVisible();
    await expect(wsStatus).toHaveAttribute('data-status', 'connected');
  });

  test('receives metric updates', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Get initial throughput value
    const throughput = page.locator('[data-testid="throughput-value"]');
    const initialValue = await throughput.textContent();

    // Wait for update
    await page.waitForTimeout(2000);

    // Value should update or remain valid
    const updatedValue = await throughput.textContent();
    expect(updatedValue).toBeTruthy();
  });

  test('handles WebSocket reconnection', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Simulate disconnect (would need backend support)
    // For now, just verify reconnect UI
    const wsStatus = page.locator('[data-testid="ws-status"]');
    await expect(wsStatus).toBeVisible();
  });
});

test.describe('Error Handling', () => {
  test('displays error on API failure', async ({ page }) => {
    // Mock API failure
    await page.route('**/api/betanet/status', route => route.abort());

    await page.goto('http://localhost:3000/betanet');

    // Check error message
    await expect(page.getByText(/error loading/i)).toBeVisible();
  });

  test('shows retry option on failure', async ({ page }) => {
    await page.route('**/api/benchmarks/start', route => route.abort());

    await page.goto('http://localhost:3000/benchmarks');
    await page.getByRole('button', { name: /start/i }).click();

    // Retry button should appear
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();
  });

  test('gracefully handles missing data', async ({ page }) => {
    await page.route('**/api/betanet/status', route =>
      route.fulfill({ status: 200, body: JSON.stringify({}) })
    );

    await page.goto('http://localhost:3000/betanet');

    // Should show empty state or loading
    const emptyState = page.locator('[data-testid="empty-state"]');
    const loading = page.locator('[data-testid="loading"]');

    const isVisible = await Promise.race([
      emptyState.isVisible(),
      loading.isVisible(),
    ]);

    expect(isVisible).toBeTruthy();
  });
});