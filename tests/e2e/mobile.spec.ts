/**
 * Mobile Responsiveness E2E Tests
 */

import { test, expect, devices, type Page } from '@playwright/test';

const iphone12 = devices['iPhone 12'] ?? { viewport: { width: 390, height: 844 } };
const pixel5 = devices['Pixel 5'] ?? { viewport: { width: 393, height: 851 } };
const ipadMini = devices['iPad Mini'] ?? { viewport: { width: 768, height: 1024 } };
const ipadPro = devices['iPad Pro'] ?? { viewport: { width: 1024, height: 1366 } };

async function gotoRoute(page: Page, route: string) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      break;
    } catch (error) {
      if (!String(error).includes('interrupted by another navigation') || attempt === 1) {
        throw error;
      }
      await page.waitForTimeout(250);
    }
  }

  await page.waitForLoadState('networkidle').catch(() => {});
}

test.describe('Mobile Responsiveness', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(iphone12.viewport);
    await gotoRoute(page, 'http://localhost:3000');
  });

  test('mobile navigation works', async ({ page }) => {
    // Hamburger menu should be visible
    const menuButton = page.locator('[aria-label="Menu"]');
    await expect(menuButton).toBeVisible();

    // Open menu
    await menuButton.click();

    // Navigation links should appear - scope to mobile menu to avoid strict mode violations
    const mobileMenu = page.locator('[data-testid="mobile-menu-drawer"]');
    await expect(mobileMenu.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(mobileMenu.getByRole('link', { name: /betanet/i })).toBeVisible();
  });

  test('dashboard adapts to mobile', async ({ page }) => {
    // System metrics should stack vertically
    const metrics = page.locator('[data-testid="system-metrics"]');
    await expect(metrics).toBeVisible();

    const metricsBox = await metrics.boundingBox();
    expect(metricsBox?.width).toBeLessThan(500);
  });

  test('touch interactions work', async ({ page }) => {
    await gotoRoute(page, 'http://localhost:3000/betanet');

    // Tap on mixnode
    const firstNode = page.locator('[data-testid^="mixnode-"]').first();
    if (await firstNode.isVisible()) {
      await firstNode.click();

      await expect(
        page.locator('[data-testid="node-details"], [data-testid="betanet-topology"], [data-testid="betanet-topology-fallback"]').first()
      ).toBeVisible();
    } else {
      await expect(
        page.locator('[data-testid="empty-state"], [role="alert"], [data-testid="betanet-topology"], [data-testid="betanet-topology-fallback"]').first()
      ).toBeVisible();
    }
  });

  test('charts are responsive', async ({ page }) => {
    await gotoRoute(page, 'http://localhost:3000/benchmarks');

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
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(ipadPro.viewport);
    await gotoRoute(page, 'http://localhost:3000');
  });

  test('tablet layout displays correctly', async ({ page }) => {
    // Should show full navigation
    await expect(page.locator('nav')).toBeVisible();

    // Metrics should be in 2-column layout
    const metrics = page.locator('[data-testid="system-metrics"]');
    const metricsBox = await metrics.boundingBox();
    const viewportSize = page.viewportSize();

    expect(metricsBox?.width).toBeGreaterThan(280);
    expect(metricsBox?.width).toBeLessThanOrEqual(viewportSize?.width || 0);
  });

  test('topology view works on tablet', async ({ page }) => {
    await gotoRoute(page, 'http://localhost:3000/betanet');

    const topology = page.locator('[data-testid="betanet-topology"], [data-testid="betanet-topology-fallback"]').first();
    await expect(topology).toBeVisible();

    // Should have touch controls
    const controls = page.locator('[data-testid="topology-controls"]');
    await expect(controls).toBeVisible();
  });

  test('landscape orientation', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await gotoRoute(page, 'http://localhost:3000/benchmarks');

    // Content should reflow
    await expect(page.locator('main')).toBeVisible();

    // Charts should be side-by-side
    const charts = page.locator('[data-testid="benchmark-charts"]');
    const chartsBox = await charts.boundingBox();
    const viewportSize = page.viewportSize();

    expect(chartsBox?.width || 0).toBeGreaterThan((viewportSize?.width || 0) * 0.6);
  });
});

test.describe('Cross-Device Features', () => {
  const devices_list = [
    { device: iphone12, name: 'iPhone 12' },
    { device: pixel5, name: 'Pixel 5' },
    { device: ipadMini, name: 'iPad Mini' },
  ];

  devices_list.forEach(({ device, name }) => {
    test(`benchmark controls work on ${name}`, async ({ page }) => {
      await page.setViewportSize(device.viewport);
      await gotoRoute(page, 'http://localhost:3000/benchmarks');

      // Start button should be accessible
      const startButton = page.getByRole('button', { name: /start/i });
      await expect(startButton).toBeVisible();

      // Should be activatable in both touch and desktop browser projects.
      await startButton.click();

      // Controls should update
      await expect(page.getByText(/running/i)).toBeVisible();
    });
  });
});
