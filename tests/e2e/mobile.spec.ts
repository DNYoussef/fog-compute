/**
 * Mobile Responsiveness E2E Tests
 */

import { test, expect, devices } from '@playwright/test';

test.describe('Mobile Responsiveness', () => {
  const iphone12 = devices['iPhone 12'];

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(iphone12.viewport);
    await page.goto('http://localhost:3000');
  });

  test('mobile navigation works', async ({ page }) => {
    // Hamburger menu should be visible
    const menuButton = page.locator('[aria-label="Menu"]');
    await expect(menuButton).toBeVisible();

    // Open menu
    await menuButton.click();

    // Navigation links should appear
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /betanet/i })).toBeVisible();
  });

  test('dashboard adapts to mobile', async ({ page }) => {
    // System metrics should stack vertically
    const metrics = page.locator('[data-testid="system-metrics"]');
    await expect(metrics).toBeVisible();

    const metricsBox = await metrics.boundingBox();
    expect(metricsBox?.width).toBeLessThan(500);
  });

  test('touch interactions work', async ({ page }) => {
    await page.goto('http://localhost:3000/betanet');

    // Tap on mixnode
    const firstNode = page.locator('[data-testid^="mixnode-"]').first();
    await firstNode.tap();

    // Details should appear
    await expect(page.locator('[data-testid="node-details"]')).toBeVisible();
  });

  test('charts are responsive', async ({ page }) => {
    await page.goto('http://localhost:3000/benchmarks');

    const chart = page.locator('[data-testid="throughput-chart"]');
    await expect(chart).toBeVisible();

    const chartBox = await chart.boundingBox();
    const viewportSize = page.viewportSize();

    // Chart should fit in viewport
    expect(chartBox?.width).toBeLessThanOrEqual(viewportSize?.width || 0);
  });

  test('modals display correctly', async ({ page }) => {
    // Open deploy modal
    await page.getByRole('button', { name: /deploy node/i }).click();

    const modal = page.locator('[data-testid="deploy-modal"]');
    await expect(modal).toBeVisible();

    // Modal should fit viewport
    const modalBox = await modal.boundingBox();
    const viewportSize = page.viewportSize();

    expect(modalBox?.width).toBeLessThanOrEqual(viewportSize?.width || 0);
    expect(modalBox?.height).toBeLessThanOrEqual(viewportSize?.height || 0);
  });
});

test.describe('Tablet Responsiveness', () => {
  const ipadPro = devices['iPad Pro'];

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(ipadPro.viewport);
    await page.goto('http://localhost:3000');
  });

  test('tablet layout displays correctly', async ({ page }) => {
    // Should show full navigation
    await expect(page.locator('nav')).toBeVisible();

    // Metrics should be in 2-column layout
    const metrics = page.locator('[data-testid="system-metrics"]');
    const metricsBox = await metrics.boundingBox();

    expect(metricsBox?.width).toBeGreaterThan(500);
    expect(metricsBox?.width).toBeLessThan(1024);
  });

  test('topology view works on tablet', async ({ page }) => {
    await page.goto('http://localhost:3000/betanet');

    const topology = page.locator('[data-testid="betanet-topology"]');
    await expect(topology).toBeVisible();

    // Should have touch controls
    const controls = page.locator('[data-testid="topology-controls"]');
    await expect(controls).toBeVisible();
  });

  test('landscape orientation', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });

    // Content should reflow
    await expect(page.locator('main')).toBeVisible();

    // Charts should be side-by-side
    const charts = page.locator('[data-testid="benchmark-charts"]');
    const chartsBox = await charts.boundingBox();

    expect(chartsBox?.width).toBeGreaterThan(700);
  });
});

test.describe('Cross-Device Features', () => {
  const devices_list = [
    { device: devices['iPhone 12'], name: 'iPhone 12' },
    { device: devices['Pixel 5'], name: 'Pixel 5' },
    { device: devices['iPad Mini'], name: 'iPad Mini' },
  ];

  devices_list.forEach(({ device, name }) => {
    test(`benchmark controls work on ${name}`, async ({ page }) => {
      await page.setViewportSize(device.viewport);
      await page.goto('http://localhost:3000/benchmarks');

      // Start button should be accessible
      const startButton = page.getByRole('button', { name: /start/i });
      await expect(startButton).toBeVisible();

      // Should be tappable
      await startButton.tap();

      // Controls should update
      await expect(page.getByText(/running/i)).toBeVisible();
    });
  });
});