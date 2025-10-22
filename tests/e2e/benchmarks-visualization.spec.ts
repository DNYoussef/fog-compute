import { test, expect } from '@playwright/test';

/**
 * Benchmarks Visualization E2E Tests
 * Tests benchmark charts, controls, and performance visualization
 */

test.describe('Benchmarks Visualization Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/benchmarks');
    await expect(page).toHaveTitle(/Benchmarks/i);
  });

  test('Complete benchmarks workflow', async ({ page }) => {
    await test.step('Load benchmarks dashboard', async () => {
      const dashboard = page.locator('[data-testid="benchmarks-dashboard"]');
      await expect(dashboard).toBeVisible({ timeout: 10000 });

      // Verify main sections
      await expect(page.locator('[data-testid="benchmark-controls"]')).toBeVisible();
      await expect(page.locator('[data-testid="charts-container"]')).toBeVisible();
      await expect(page.locator('[data-testid="stats-summary"]')).toBeVisible();
    });

    await test.step('Run CPU benchmark', async () => {
      await page.click('[data-testid="cpu-benchmark-button"]');

      // Configure benchmark
      await page.fill('[data-testid="duration-input"]', '30');
      await page.selectOption('[data-testid="workload-select"]', 'intensive');
      await page.fill('[data-testid="threads-input"]', '4');

      await page.click('[data-testid="start-benchmark-button"]');

      // Monitor progress
      const progress = page.locator('[data-testid="benchmark-progress"]');
      await expect(progress).toBeVisible();

      const progressBar = page.locator('[data-testid="progress-bar"]');
      await expect(progressBar).toHaveAttribute('aria-valuenow', '0');

      // Wait for completion
      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Completed', { timeout: 60000 });
      await expect(progressBar).toHaveAttribute('aria-valuenow', '100');
    });

    await test.step('View CPU benchmark results', async () => {
      const results = page.locator('[data-testid="cpu-benchmark-results"]');
      await expect(results).toBeVisible();

      // Verify metrics
      await expect(results.locator('[data-testid="cpu-score"]')).toContainText(/\d+/);
      await expect(results.locator('[data-testid="ops-per-second"]')).toContainText(/\d+/);
      await expect(results.locator('[data-testid="avg-latency"]')).toContainText(/\d+/);

      // Verify chart
      const chart = page.locator('[data-testid="cpu-performance-chart"]');
      await expect(chart).toBeVisible();
    });

    await test.step('Run memory benchmark', async () => {
      await page.click('[data-testid="memory-benchmark-button"]');

      await page.selectOption('[data-testid="memory-test-type"]', 'bandwidth');
      await page.fill('[data-testid="buffer-size-input"]', '1024');

      await page.click('[data-testid="start-benchmark-button"]');

      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Running');
      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Completed', { timeout: 60000 });

      // Verify results
      const memResults = page.locator('[data-testid="memory-benchmark-results"]');
      await expect(memResults.locator('[data-testid="read-bandwidth"]')).toContainText(/\d+/);
      await expect(memResults.locator('[data-testid="write-bandwidth"]')).toContainText(/\d+/);
    });
  });

  test.skip('Interactive charts and controls', async ({ page }) => {
    await test.step('Customize chart display', async () => {
      // Run a quick benchmark first
      await page.click('[data-testid="quick-benchmark-button"]');
      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Completed', { timeout: 30000 });

      // Chart controls
      await page.selectOption('[data-testid="chart-type-select"]', 'line');
      await expect(page.locator('[data-testid="main-chart"]')).toHaveAttribute('data-chart-type', 'line');

      // Change to bar chart
      await page.selectOption('[data-testid="chart-type-select"]', 'bar');
      await expect(page.locator('[data-testid="main-chart"]')).toHaveAttribute('data-chart-type', 'bar');
    });

    await test.step('Zoom and pan charts', async () => {
      const chart = page.locator('[data-testid="main-chart"]');

      // Zoom in
      await page.click('[data-testid="zoom-in-button"]');
      await page.waitForTimeout(500);

      // Zoom out
      await page.click('[data-testid="zoom-out-button"]');
      await page.waitForTimeout(500);

      // Reset zoom
      await page.click('[data-testid="reset-zoom-button"]');
    });

    await test.step('Toggle chart series', async () => {
      await page.click('[data-testid="legend-cpu"]');
      await expect(page.locator('[data-testid="cpu-series"]')).not.toBeVisible();

      await page.click('[data-testid="legend-cpu"]');
      await expect(page.locator('[data-testid="cpu-series"]')).toBeVisible();
    });

    await test.step('Hover for tooltips', async () => {
      const chartArea = page.locator('[data-testid="chart-canvas"]');
      await chartArea.hover({ position: { x: 100, y: 100 } });

      const tooltip = page.locator('[data-testid="chart-tooltip"]');
      await expect(tooltip).toBeVisible({ timeout: 2000 });
      await expect(tooltip).toContainText(/\d+/);
    });
  });

  test.skip('Time series and historical data', async ({ page }) => {
    await test.step('View historical benchmarks', async () => {
      await page.click('[data-testid="historical-data-tab"]');

      const historyTable = page.locator('[data-testid="benchmark-history"]');
      await expect(historyTable).toBeVisible();

      const rows = page.locator('[data-testid="history-row"]');
      const count = await rows.count();
      expect(count).toBeGreaterThan(0);
    });

    await test.step('Filter by time range', async () => {
      await page.selectOption('[data-testid="time-range-select"]', '7d');
      await page.waitForTimeout(1000);

      // Verify chart updates
      const dataPoints = page.locator('[data-testid="chart-data-point"]');
      await expect(dataPoints.first()).toBeVisible();
    });

    await test.step('Compare time periods', async () => {
      await page.check('[data-testid="compare-periods-checkbox"]');

      await page.selectOption('[data-testid="compare-period-1"]', 'last_week');
      await page.selectOption('[data-testid="compare-period-2"]', 'this_week');

      const comparisonChart = page.locator('[data-testid="comparison-chart"]');
      await expect(comparisonChart).toBeVisible();

      // Verify multiple series
      await expect(page.locator('[data-testid="series-last-week"]')).toBeVisible();
      await expect(page.locator('[data-testid="series-this-week"]')).toBeVisible();
    });
  });

  test.skip('Export and report generation', async ({ page }) => {
    await test.step('Generate benchmark report', async () => {
      // Run benchmark first
      await page.click('[data-testid="quick-benchmark-button"]');
      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Completed', { timeout: 30000 });

      await page.click('[data-testid="generate-report-button"]');

      const reportModal = page.locator('[data-testid="report-modal"]');
      await expect(reportModal).toBeVisible();

      // Configure report
      await page.fill('[data-testid="report-title-input"]', 'E2E Test Report');
      await page.check('[data-testid="include-charts-checkbox"]');
      await page.check('[data-testid="include-raw-data-checkbox"]');
      await page.selectOption('[data-testid="report-format-select"]', 'pdf');

      await page.click('[data-testid="generate-button"]');

      // Wait for generation
      await expect(page.locator('[data-testid="report-status"]')).toHaveText('Generating...', { timeout: 2000 });
      await expect(page.locator('[data-testid="report-status"]')).toHaveText('Ready', { timeout: 30000 });
    });

    await test.step('Download report', async () => {
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.click('[data-testid="download-report-button"]')
      ]);

      expect(download.suggestedFilename()).toMatch(/E2E.*\.pdf$/);
    });

    await test.step('Export chart as image', async () => {
      await page.click('[data-testid="export-chart-button"]');

      await page.selectOption('[data-testid="image-format-select"]', 'png');
      await page.fill('[data-testid="image-width-input"]', '1920');
      await page.fill('[data-testid="image-height-input"]', '1080');

      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.click('[data-testid="export-image-button"]')
      ]);

      expect(download.suggestedFilename()).toMatch(/\.png$/);
    });

    await test.step('Export data as CSV', async () => {
      await page.click('[data-testid="export-data-button"]');
      await page.selectOption('[data-testid="export-format-select"]', 'csv');

      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.click('[data-testid="confirm-export-button"]')
      ]);

      expect(download.suggestedFilename()).toMatch(/\.csv$/);
    });
  });

  test.skip('Real-time benchmark monitoring', async ({ page }) => {
    await test.step('Enable live monitoring', async () => {
      await page.check('[data-testid="live-monitoring-toggle"]');

      const liveChart = page.locator('[data-testid="live-chart"]');
      await expect(liveChart).toBeVisible();

      await expect(page.locator('[data-testid="live-status"]')).toHaveText('Live');
    });

    await test.step('Monitor real-time metrics', async () => {
      const initialDataPoints = await page.locator('[data-testid="live-data-point"]').count();

      // Wait for new data points
      await page.waitForTimeout(3000);

      const updatedDataPoints = await page.locator('[data-testid="live-data-point"]').count();
      expect(updatedDataPoints).toBeGreaterThan(initialDataPoints);
    });

    await test.step('Set performance alerts', async () => {
      await page.click('[data-testid="alerts-tab"]');
      await page.click('[data-testid="add-alert-button"]');

      await page.fill('[data-testid="alert-name-input"]', 'High CPU Alert');
      await page.selectOption('[data-testid="metric-select"]', 'cpu_usage');
      await page.selectOption('[data-testid="condition-select"]', 'greater_than');
      await page.fill('[data-testid="threshold-input"]', '90');

      await page.click('[data-testid="save-alert-button"]');

      await expect(page.locator('[data-testid="alert-item"]', { hasText: 'High CPU Alert' })).toBeVisible();
    });
  });

  test.skip('Multi-benchmark comparison', async ({ page }) => {
    await test.step('Select benchmarks to compare', async () => {
      await page.click('[data-testid="comparison-mode-button"]');

      // Select multiple benchmark results
      await page.check('[data-testid="benchmark-checkbox"][data-id="1"]');
      await page.check('[data-testid="benchmark-checkbox"][data-id="2"]');
      await page.check('[data-testid="benchmark-checkbox"][data-id="3"]');

      await page.click('[data-testid="compare-selected-button"]');
    });

    await test.step('View comparison visualization', async () => {
      const comparisonView = page.locator('[data-testid="comparison-view"]');
      await expect(comparisonView).toBeVisible();

      // Verify comparison charts
      await expect(page.locator('[data-testid="comparison-bar-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="comparison-table"]')).toBeVisible();

      // Check metrics comparison
      await expect(page.locator('[data-testid="metric-delta"]')).toHaveCount({ min: 1 });
    });

    await test.step('Analyze performance trends', async () => {
      await page.click('[data-testid="trends-tab"]');

      const trendChart = page.locator('[data-testid="trend-chart"]');
      await expect(trendChart).toBeVisible();

      // Verify trend line
      await expect(page.locator('[data-testid="trend-line"]')).toBeVisible();

      // Check trend statistics
      await expect(page.locator('[data-testid="trend-direction"]')).toContainText(/Improving|Declining|Stable/i);
      await expect(page.locator('[data-testid="trend-percentage"]')).toContainText(/\d+%/);
    });
  });

  test.skip('Benchmark configuration presets', async ({ page }) => {
    await test.step('Load preset configuration', async () => {
      await page.click('[data-testid="presets-button"]');

      const presetsMenu = page.locator('[data-testid="presets-menu"]');
      await expect(presetsMenu).toBeVisible();

      await page.click('[data-testid="preset-option"][data-preset="stress-test"]');

      // Verify configuration loaded
      await expect(page.locator('[data-testid="duration-input"]')).toHaveValue('300');
      await expect(page.locator('[data-testid="workload-select"]')).toHaveValue('maximum');
    });

    await test.step('Save custom preset', async () => {
      // Configure custom settings
      await page.fill('[data-testid="duration-input"]', '120');
      await page.selectOption('[data-testid="workload-select"]', 'moderate');
      await page.fill('[data-testid="threads-input"]', '8');

      await page.click('[data-testid="save-preset-button"]');

      await page.fill('[data-testid="preset-name-input"]', 'E2E Custom Preset');
      await page.click('[data-testid="confirm-save-preset-button"]');

      // Verify preset saved
      await page.click('[data-testid="presets-button"]');
      await expect(page.locator('[data-testid="preset-option"][data-preset="E2E Custom Preset"]')).toBeVisible();
    });
  });
});