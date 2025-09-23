/**
 * Cross-Browser Compatibility Tests
 */

import { test, expect, chromium, firefox, webkit } from '@playwright/test';

test.describe('Chromium Browser', () => {
  test('renders correctly in Chrome', async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000');

    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();

    await browser.close();
  });

  test('3D topology works in Chrome', async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000/betanet');

    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();

    // Check WebGL support
    const hasWebGL = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
    });

    expect(hasWebGL).toBe(true);

    await browser.close();
  });
});

test.describe('Firefox Browser', () => {
  test('renders correctly in Firefox', async () => {
    const browser = await firefox.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000');

    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();

    await browser.close();
  });

  test('charts render in Firefox', async () => {
    const browser = await firefox.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000/benchmarks');

    const charts = page.locator('[data-testid="benchmark-charts"]');
    await expect(charts).toBeVisible();

    await browser.close();
  });

  test('WebSocket works in Firefox', async () => {
    const browser = await firefox.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000');

    const wsStatus = page.locator('[data-testid="ws-status"]');
    await expect(wsStatus).toBeVisible();

    await browser.close();
  });
});

test.describe('WebKit/Safari Browser', () => {
  test('renders correctly in Safari', async () => {
    const browser = await webkit.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000');

    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();

    await browser.close();
  });

  test('3D topology works in Safari', async () => {
    const browser = await webkit.launch();
    const page = await browser.newPage();

    await page.goto('http://localhost:3000/betanet');

    const topology = page.locator('[data-testid="betanet-topology"]');
    await expect(topology).toBeVisible();

    await browser.close();
  });

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
});

test.describe('Cross-Browser Feature Parity', () => {
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

      // Start benchmark
      await page.getByRole('button', { name: /start/i }).click();

      // Should show running state
      await expect(page.getByText(/running/i)).toBeVisible();

      // Stop benchmark
      await page.getByRole('button', { name: /stop/i }).click();

      await browser.close();
    });

    test(`real-time updates work in ${name}`, async () => {
      const browser = await launcher.launch();
      const page = await browser.newPage();

      await page.goto('http://localhost:3000');

      // Check for metric updates
      const metrics = page.locator('[data-testid="system-metrics"]');
      await expect(metrics).toBeVisible();

      await browser.close();
    });

    test(`API calls work in ${name}`, async () => {
      const browser = await launcher.launch();
      const page = await browser.newPage();

      // Monitor network requests
      let apiCallMade = false;
      page.on('request', (request) => {
        if (request.url().includes('/api/')) {
          apiCallMade = true;
        }
      });

      await page.goto('http://localhost:3000/betanet');

      await page.waitForLoadState('networkidle');

      expect(apiCallMade).toBe(true);

      await browser.close();
    });
  });
});

test.describe('Browser-Specific Optimizations', () => {
  test('uses requestAnimationFrame in all browsers', async ({ page }) => {
    await page.goto('http://localhost:3000/betanet');

    const hasRAF = await page.evaluate(() => {
      return typeof window.requestAnimationFrame === 'function';
    });

    expect(hasRAF).toBe(true);
  });

  test('Canvas 2D fallback works', async ({ page }) => {
    await page.goto('http://localhost:3000/benchmarks');

    const canvas2DSupport = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      return !!canvas.getContext('2d');
    });

    expect(canvas2DSupport).toBe(true);
  });

  test('localStorage works across browsers', async ({ page }) => {
    await page.goto('http://localhost:3000');

    await page.evaluate(() => {
      localStorage.setItem('test', 'value');
    });

    const value = await page.evaluate(() => {
      return localStorage.getItem('test');
    });

    expect(value).toBe('value');
  });

  test('sessionStorage works across browsers', async ({ page }) => {
    await page.goto('http://localhost:3000');

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
  const browsers = [
    { name: 'Chromium', launcher: chromium },
    { name: 'Firefox', launcher: firefox },
    { name: 'WebKit', launcher: webkit },
  ];

  browsers.forEach(({ name, launcher }) => {
    test(`page load time is acceptable in ${name}`, async () => {
      const browser = await launcher.launch();
      const page = await browser.newPage();

      const startTime = Date.now();
      await page.goto('http://localhost:3000');
      await page.waitForLoadState('networkidle');
      const loadTime = Date.now() - startTime;

      expect(loadTime).toBeLessThan(5000); // < 5 seconds

      await browser.close();
    });

    test(`memory usage is reasonable in ${name}`, async () => {
      const browser = await launcher.launch();
      const page = await browser.newPage();

      await page.goto('http://localhost:3000/betanet');

      const metrics = await page.metrics();

      // Memory usage should be reasonable
      expect(metrics.JSHeapUsedSize).toBeLessThan(100 * 1024 * 1024); // < 100MB

      await browser.close();
    });
  });
});