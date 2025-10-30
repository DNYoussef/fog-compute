/**
 * Cross-Browser Compatibility Tests
 *
 * These tests use Playwright's project-based execution model.
 * Each test runs once per configured browser project (chromium, firefox, webkit).
 * The { page } fixture is automatically provided with the correct browser.
 *
 * Configuration: playwright.config.ts defines projects for each browser.
 * Usage: npx playwright test cross-browser.spec.ts --project=chromium
 */

import { test, expect } from '@playwright/test';

test.describe('Basic Browser Rendering', () => {
  test('renders correctly across all browsers', async ({ page, browserName }) => {
    // This test runs once per browser project (chromium, firefox, webkit)
    // Playwright handles browser instantiation through projects
    await page.goto('/');

    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();
  });

  test('3D topology works across browsers', async ({ page, browserName }) => {
    // Each browser project runs this test with its own browser instance
    await page.goto('/betanet');

    // For Chromium, check canvas element
    if (browserName === 'chromium') {
      const canvas = page.locator('canvas');
      await expect(canvas).toBeVisible();

      // Check WebGL support in Chromium
      const hasWebGL = await page.evaluate(() => {
        const canvas = document.createElement('canvas');
        return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
      });

      expect(hasWebGL).toBe(true);
    } else {
      // For Firefox and WebKit, check topology element
      const topology = page.locator('[data-testid="betanet-topology"]');
      await expect(topology).toBeVisible();
    }
  });
});

test.describe('Browser-Specific Features', () => {
  test('charts render correctly', async ({ page }) => {
    await page.goto('/benchmarks');

    const charts = page.locator('[data-testid="benchmark-charts"]');
    await expect(charts).toBeVisible();
  });

  test('WebSocket connection works', async ({ page }) => {
    await page.goto('/');

    const wsStatus = page.locator('[data-testid="ws-status"]');
    await expect(wsStatus).toBeVisible();
  });

  test('touch events work on mobile browsers', async ({ page, browserName, context }) => {
    // Touch events are primarily for WebKit/Safari
    // Use context to enable touch if needed
    await page.goto('/betanet');

    const firstNode = page.locator('[data-testid^="mixnode-"]').first();

    // Use tap for touch-enabled browsers, click for others
    if (browserName === 'webkit') {
      await firstNode.tap();
    } else {
      await firstNode.click();
    }

    await expect(page.locator('[data-testid="node-details"]')).toBeVisible();
  });
});

test.describe('Cross-Browser Feature Parity', () => {
  // These tests run once per browser project (chromium, firefox, webkit)
  // No need for browser loops - Playwright handles this via project configuration

  test('benchmark execution works across all browsers', async ({ page, browserName }) => {
    // This test runs on all browser projects automatically
    await page.goto('/benchmarks');

    // Start benchmark
    await page.getByRole('button', { name: /start/i }).click();

    // Should show running state
    await expect(page.getByText(/running/i)).toBeVisible();

    // Stop benchmark
    await page.getByRole('button', { name: /stop/i }).click();
  });

  test('real-time updates work across all browsers', async ({ page, browserName }) => {
    // Each browser project runs this test independently
    await page.goto('/');

    // Check for metric updates
    const metrics = page.locator('[data-testid="system-metrics"]');
    await expect(metrics).toBeVisible();
  });

  test('API calls work across all browsers', async ({ page, browserName }) => {
    // Monitor network requests
    let apiCallMade = false;
    page.on('request', (request) => {
      if (request.url().includes('/api/')) {
        apiCallMade = true;
      }
    });

    await page.goto('/betanet');

    await page.waitForLoadState('networkidle');

    expect(apiCallMade).toBe(true);
  });
});

test.describe('Browser-Specific Optimizations', () => {
  test('uses requestAnimationFrame in all browsers', async ({ page }) => {
    // Uses relative path with baseURL from playwright.config.ts
    await page.goto('/betanet');

    const hasRAF = await page.evaluate(() => {
      return typeof window.requestAnimationFrame === 'function';
    });

    expect(hasRAF).toBe(true);
  });

  test('Canvas 2D fallback works', async ({ page }) => {
    await page.goto('/benchmarks');

    const canvas2DSupport = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      return !!canvas.getContext('2d');
    });

    expect(canvas2DSupport).toBe(true);
  });

  test('localStorage works across browsers', async ({ page }) => {
    await page.goto('/');

    await page.evaluate(() => {
      localStorage.setItem('test', 'value');
    });

    const value = await page.evaluate(() => {
      return localStorage.getItem('test');
    });

    expect(value).toBe('value');
  });

  test('sessionStorage works across browsers', async ({ page }) => {
    await page.goto('/');

    await page.evaluate(() => {
      sessionStorage.setItem('session-test', 'session-value');
    });

    const value = await page.evaluate(() => {
      return sessionStorage.getItem('session-test');
    });

    expect(value).toBe('session-value');
  });
});

test.describe('Performance Across Browsers', () => {
  // These tests run once per browser project
  // Playwright's project configuration handles browser instantiation

  test('page load time is acceptable across all browsers', async ({ page, browserName }) => {
    // Each browser project runs this test independently
    const startTime = Date.now();
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;

    expect(loadTime).toBeLessThan(5000); // < 5 seconds
  });

  test('memory usage is reasonable', async ({ page, browserName }) => {
    // Skip metrics test for WebKit as page.metrics() is not supported
    // page.metrics() only supported in Chromium and Firefox
    if (browserName === 'webkit') {
      test.skip();
      return;
    }

    await page.goto('/betanet');

    const metrics = await page.metrics();

    // Memory usage should be reasonable
    expect(metrics.JSHeapUsedSize).toBeLessThan(100 * 1024 * 1024); // < 100MB
  });
});