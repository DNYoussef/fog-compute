import { test, expect, devices } from '@playwright/test';

/**
 * Mobile and Responsive Testing
 * Tests mobile viewports, touch interactions, and responsive layouts
 */

const mobileDevices = [
  { name: 'iPhone 12', ...devices['iPhone 12'] },
  { name: 'iPhone 12 Pro Max', ...devices['iPhone 12 Pro Max'] },
  { name: 'Pixel 5', ...devices['Pixel 5'] },
  { name: 'Samsung Galaxy S21', ...devices['Galaxy S9+'] },
  { name: 'iPad Pro', ...devices['iPad Pro'] },
];

test.describe('Mobile Responsive Design', () => {
  for (const device of mobileDevices.slice(0, 2)) { // Test first 2 devices
    test.describe(`${device.name}`, () => {
      test.use({ ...device });

      test('Should display mobile-optimized layout', async ({ page }) => {
        await page.goto('/');

        // Verify mobile menu
        const mobileMenu = page.locator('[data-testid="mobile-menu"]');
        await expect(mobileMenu).toBeVisible();

        // Verify desktop nav is hidden
        const desktopNav = page.locator('[data-testid="desktop-nav"]');
        await expect(desktopNav).not.toBeVisible();

        // Check viewport-specific styles
        const mainContent = page.locator('[data-testid="main-content"]');
        const width = await mainContent.evaluate(el => window.getComputedStyle(el).width);
        expect(parseInt(width)).toBeLessThan(device.viewport.width);
      });

      test('Should have touch-friendly targets', async ({ page }) => {
        await page.goto('/');

        const buttons = page.locator('button, a[href]');
        const count = await buttons.count();

        for (let i = 0; i < Math.min(count, 5); i++) {
          const button = buttons.nth(i);
          const box = await button.boundingBox();

          if (box) {
            // Touch targets should be at least 44x44px (WCAG)
            expect(box.width).toBeGreaterThanOrEqual(44);
            expect(box.height).toBeGreaterThanOrEqual(44);
          }
        }
      });

      test('Should support touch gestures', async ({ page }) => {
        await page.goto('/control-panel');

        // Swipe gesture for navigation
        const swipeArea = page.locator('[data-testid="swipe-nav"]');
        if (await swipeArea.isVisible()) {
          await swipeArea.touchscreen.swipe({ x: 300, y: 200 }, { x: 50, y: 200 });
          await page.waitForTimeout(500);

          // Verify navigation changed
          const activeTab = page.locator('[data-testid="tab"][aria-selected="true"]');
          await expect(activeTab).toBeVisible();
        }
      });

      test('Should handle mobile menu interactions', async ({ page }) => {
        await page.goto('/');

        // Open mobile menu
        const menuButton = page.locator('[data-testid="mobile-menu-button"]');
        await menuButton.tap();

        const menu = page.locator('[data-testid="mobile-menu-drawer"]');
        await expect(menu).toBeVisible();

        // Navigate via menu
        await page.locator('[data-testid="menu-item"][data-route="/nodes"]').tap();

        await expect(page).toHaveURL(/\/nodes/);
        await expect(menu).not.toBeVisible(); // Menu should close
      });
    });
  }

  test.describe('Responsive Breakpoints', () => {
    const breakpoints = [
      { width: 320, height: 568, name: 'Small Mobile' },
      { width: 375, height: 667, name: 'Mobile' },
      { width: 768, height: 1024, name: 'Tablet Portrait' },
      { width: 1024, height: 768, name: 'Tablet Landscape' },
      { width: 1366, height: 768, name: 'Desktop' },
      { width: 1920, height: 1080, name: 'Large Desktop' },
    ];

    for (const bp of breakpoints) {
      test(`Should adapt to ${bp.name} (${bp.width}x${bp.height})`, async ({ page }) => {
        await page.setViewportSize({ width: bp.width, height: bp.height });
        await page.goto('/');

        // Verify responsive classes
        const body = page.locator('body');
        const className = await body.getAttribute('class');

        if (bp.width < 768) {
          expect(className).toContain('mobile');
        } else if (bp.width < 1024) {
          expect(className).toContain('tablet');
        } else {
          expect(className).toContain('desktop');
        }

        // Verify layout adjustments
        const grid = page.locator('[data-testid="main-grid"]');
        if (await grid.isVisible()) {
          const gridCols = await grid.evaluate(el =>
            window.getComputedStyle(el).gridTemplateColumns
          );

          if (bp.width < 768) {
            expect(gridCols).toContain('1fr'); // Single column
          }
        }
      });
    }
  });

  test.describe('Mobile-Specific Features', () => {
    test.use({ ...devices['iPhone 12'] });

    test('Should support pull-to-refresh', async ({ page }) => {
      await page.goto('/nodes');

      const listContainer = page.locator('[data-testid="nodes-list"]');

      // Simulate pull-to-refresh
      await listContainer.touchscreen.swipe({ x: 200, y: 100 }, { x: 200, y: 400 });

      // Verify refresh indicator
      const refreshIndicator = page.locator('[data-testid="refresh-indicator"]');
      await expect(refreshIndicator).toBeVisible({ timeout: 2000 });

      // Wait for refresh completion
      await expect(refreshIndicator).not.toBeVisible({ timeout: 10000 });
    });

    test('Should display bottom navigation on mobile', async ({ page }) => {
      await page.goto('/');

      const bottomNav = page.locator('[data-testid="bottom-navigation"]');
      await expect(bottomNav).toBeVisible();

      // Verify position
      const position = await bottomNav.evaluate(el =>
        window.getComputedStyle(el).position
      );
      expect(position).toBe('fixed');

      // Test navigation
      await page.locator('[data-testid="nav-item"][data-route="/tasks"]').tap();
      await expect(page).toHaveURL(/\/tasks/);
    });

    test('Should optimize images for mobile', async ({ page }) => {
      await page.goto('/');

      const images = page.locator('img[srcset]');
      const count = await images.count();

      for (let i = 0; i < Math.min(count, 3); i++) {
        const img = images.nth(i);
        const srcset = await img.getAttribute('srcset');

        // Should have multiple image sources
        expect(srcset).toBeTruthy();
        expect(srcset).toContain('w'); // Width descriptor
      }
    });

    test('Should handle orientation changes', async ({ page }) => {
      await page.goto('/');

      // Portrait mode
      await page.setViewportSize({ width: 375, height: 812 });
      await page.waitForTimeout(500);

      let layout = await page.locator('[data-testid="main-layout"]').getAttribute('data-orientation');
      expect(layout).toBe('portrait');

      // Landscape mode
      await page.setViewportSize({ width: 812, height: 375 });
      await page.waitForTimeout(500);

      layout = await page.locator('[data-testid="main-layout"]').getAttribute('data-orientation');
      expect(layout).toBe('landscape');
    });
  });

  test.describe('Mobile Form Interactions', () => {
    test.use({ ...devices['Pixel 5'] });

    test('Should optimize forms for mobile', async ({ page }) => {
      await page.goto('/nodes');
      await page.tap('[data-testid="add-node-button"]');

      // Verify mobile keyboard opens
      const nameInput = page.locator('[data-testid="node-name-input"]');
      await nameInput.tap();

      // Check input attributes
      const inputType = await nameInput.getAttribute('type');
      const autocomplete = await nameInput.getAttribute('autocomplete');

      expect(['text', 'tel', 'email']).toContain(inputType);
      expect(autocomplete).toBeTruthy();
    });

    test('Should support native date/time pickers', async ({ page }) => {
      await page.goto('/tasks');
      await page.tap('[data-testid="schedule-task-button"]');

      const dateInput = page.locator('[data-testid="schedule-date-input"]');
      const inputType = await dateInput.getAttribute('type');

      expect(['date', 'datetime-local']).toContain(inputType);
    });

    test('Should handle virtual keyboard', async ({ page }) => {
      await page.goto('/');
      await page.tap('[data-testid="search-button"]');

      const searchInput = page.locator('[data-testid="search-input"]');
      await searchInput.tap();

      // Verify input is visible when keyboard opens
      const box = await searchInput.boundingBox();
      expect(box).toBeTruthy();
      if (box) {
        expect(box.y).toBeGreaterThan(0);
      }
    });
  });

  test.describe('Tablet Experience', () => {
    test.use({ ...devices['iPad Pro'] });

    test('Should use hybrid desktop/mobile layout', async ({ page }) => {
      await page.goto('/');

      // Should show sidebar and main content
      await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
      await expect(page.locator('[data-testid="main-content"]')).toBeVisible();

      // But mobile menu should also be available
      await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeVisible();
    });

    test('Should support split-screen layouts', async ({ page }) => {
      await page.goto('/nodes');

      const splitView = page.locator('[data-testid="split-view"]');
      if (await splitView.isVisible()) {
        await expect(page.locator('[data-testid="master-pane"]')).toBeVisible();
        await expect(page.locator('[data-testid="detail-pane"]')).toBeVisible();

        // Select item in master
        await page.tap('[data-testid="node-item"]').first();

        // Details should show in detail pane
        await expect(page.locator('[data-testid="detail-pane"] [data-testid="node-details"]')).toBeVisible();
      }
    });

    test('Should support multi-touch gestures', async ({ page }) => {
      await page.goto('/betanet');

      const canvas = page.locator('[data-testid="network-topology"] canvas');
      if (await canvas.isVisible()) {
        // Pinch to zoom (simulated)
        await canvas.touchscreen.tap({ x: 300, y: 300 });
        await page.keyboard.press('Control+Plus');

        await page.waitForTimeout(500);

        // Verify zoom level changed
        const zoomLevel = await page.evaluate(() =>
          (window as any).networkTopology?.getZoomLevel()
        );

        if (zoomLevel !== undefined) {
          expect(zoomLevel).toBeGreaterThan(1);
        }
      }
    });
  });

  test.describe('Mobile Performance', () => {
    test.use({ ...devices['iPhone 12'] });

    test('Should load quickly on mobile', async ({ page }) => {
      const startTime = Date.now();

      await page.goto('/', { waitUntil: 'networkidle' });

      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(5000); // 5s on mobile
    });

    test('Should lazy load images', async ({ page }) => {
      await page.goto('/');

      // Scroll down
      await page.evaluate(() => window.scrollTo(0, 1000));
      await page.waitForTimeout(1000);

      const lazyImages = page.locator('img[loading="lazy"]');
      const count = await lazyImages.count();

      if (count > 0) {
        const firstImage = lazyImages.first();
        const isLoaded = await firstImage.evaluate(img =>
          (img as HTMLImageElement).complete
        );
        expect(isLoaded).toBeTruthy();
      }
    });

    test('Should use optimized assets', async ({ page }) => {
      await page.goto('/');

      // Check for WebP support
      const images = page.locator('img[src*=".webp"], img[srcset*=".webp"]');
      const webpCount = await images.count();

      if (webpCount > 0) {
        const firstWebP = images.first();
        const src = await firstWebP.getAttribute('src');
        expect(src).toContain('.webp');
      }
    });
  });
});