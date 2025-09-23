import { test, expect, Page } from '@playwright/test';

/**
 * Betanet Network Monitoring E2E Tests
 * Tests network visualization, node monitoring, and betanet operations
 */

test.describe('Betanet Network Visualization', () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
  });

  test.afterAll(async () => {
    await page.close();
  });

  test('Complete betanet monitoring workflow', async () => {
    await test.step('Load betanet dashboard', async () => {
      await page.goto('/betanet');
      await expect(page).toHaveTitle(/Betanet/i);

      const dashboard = page.locator('[data-testid="betanet-dashboard"]');
      await expect(dashboard).toBeVisible({ timeout: 10000 });
    });

    await test.step('Verify network topology visualization', async () => {
      const topology = page.locator('[data-testid="network-topology"]');
      await expect(topology).toBeVisible();

      // Check for SVG or Canvas rendering
      const svgOrCanvas = page.locator('[data-testid="network-topology"] svg, [data-testid="network-topology"] canvas');
      await expect(svgOrCanvas).toBeVisible();

      // Verify nodes are rendered
      const nodes = page.locator('[data-testid="network-node"]');
      const nodeCount = await nodes.count();
      expect(nodeCount).toBeGreaterThan(0);

      // Verify edges/connections
      const edges = page.locator('[data-testid="network-edge"]');
      const edgeCount = await edges.count();
      expect(edgeCount).toBeGreaterThan(0);
    });

    await test.step('Interact with network nodes', async () => {
      const firstNode = page.locator('[data-testid="network-node"]').first();
      await firstNode.click();

      // Verify node details panel
      const nodeDetails = page.locator('[data-testid="node-details-panel"]');
      await expect(nodeDetails).toBeVisible();

      await expect(page.locator('[data-testid="node-id"]')).toBeVisible();
      await expect(page.locator('[data-testid="node-status"]')).toBeVisible();
      await expect(page.locator('[data-testid="node-connections"]')).toBeVisible();
      await expect(page.locator('[data-testid="node-metrics"]')).toBeVisible();
    });

    await test.step('Monitor real-time network updates', async () => {
      // Enable real-time monitoring
      await page.check('[data-testid="realtime-monitoring-toggle"]');

      const updateIndicator = page.locator('[data-testid="last-update-timestamp"]');
      const initialTime = await updateIndicator.textContent();

      // Wait for update
      await page.waitForTimeout(3000);

      const updatedTime = await updateIndicator.textContent();
      expect(updatedTime).not.toBe(initialTime);

      // Verify network stats are updating
      const statsPanel = page.locator('[data-testid="network-stats"]');
      await expect(statsPanel.locator('[data-testid="active-nodes"]')).toContainText(/\d+/);
      await expect(statsPanel.locator('[data-testid="total-connections"]')).toContainText(/\d+/);
      await expect(statsPanel.locator('[data-testid="network-throughput"]')).toContainText(/\d+/);
    });

    await test.step('Filter and search network', async () => {
      // Filter by node status
      await page.selectOption('[data-testid="status-filter"]', 'active');
      await page.waitForTimeout(500);

      const visibleNodes = page.locator('[data-testid="network-node"]:visible');
      const count = await visibleNodes.count();
      expect(count).toBeGreaterThan(0);

      // Search for specific node
      await page.fill('[data-testid="node-search-input"]', 'node-1');
      await page.waitForTimeout(500);

      const searchResults = page.locator('[data-testid="search-results"]');
      await expect(searchResults).toBeVisible();
      await expect(searchResults.locator('[data-testid="result-item"]')).toHaveCount({ min: 1 });
    });

    await test.step('Analyze network metrics', async () => {
      await page.click('[data-testid="metrics-tab"]');

      // Verify metric charts
      await expect(page.locator('[data-testid="latency-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="bandwidth-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="packet-loss-chart"]')).toBeVisible();

      // Check time range selector
      await page.selectOption('[data-testid="time-range-select"]', '1h');
      await page.waitForTimeout(1000);

      // Verify charts update
      const chartData = await page.locator('[data-testid="latency-chart"]').getAttribute('data-updated');
      expect(chartData).toBeTruthy();
    });
  });

  test('Network path tracing and diagnostics', async () => {
    await test.step('Navigate to path tracing', async () => {
      await page.goto('/betanet/trace');
      await expect(page.locator('[data-testid="path-trace-tool"]')).toBeVisible();
    });

    await test.step('Execute path trace', async () => {
      await page.selectOption('[data-testid="source-node-select"]', 'node-1');
      await page.selectOption('[data-testid="target-node-select"]', 'node-5');
      await page.click('[data-testid="trace-path-button"]');

      // Wait for trace completion
      await expect(page.locator('[data-testid="trace-status"]')).toHaveText('Tracing...', { timeout: 2000 });
      await expect(page.locator('[data-testid="trace-status"]')).toHaveText('Complete', { timeout: 30000 });

      // Verify path visualization
      const pathViz = page.locator('[data-testid="path-visualization"]');
      await expect(pathViz).toBeVisible();

      const hops = page.locator('[data-testid="path-hop"]');
      const hopCount = await hops.count();
      expect(hopCount).toBeGreaterThan(0);

      // Verify hop details
      await expect(page.locator('[data-testid="total-latency"]')).toContainText(/\d+ms/);
      await expect(page.locator('[data-testid="hop-count"]')).toContainText(/\d+/);
    });

    await test.step('Run network diagnostics', async () => {
      await page.click('[data-testid="diagnostics-tab"]');
      await page.click('[data-testid="run-diagnostics-button"]');

      // Monitor diagnostic tests
      await expect(page.locator('[data-testid="ping-test-status"]')).toHaveText(/Running|Complete/i, { timeout: 10000 });
      await expect(page.locator('[data-testid="bandwidth-test-status"]')).toHaveText(/Running|Complete/i, { timeout: 10000 });
      await expect(page.locator('[data-testid="latency-test-status"]')).toHaveText(/Running|Complete/i, { timeout: 10000 });

      // Verify results
      const results = page.locator('[data-testid="diagnostic-results"]');
      await expect(results).toBeVisible();
      await expect(results.locator('[data-testid="ping-result"]')).toContainText(/\d+ms/);
      await expect(results.locator('[data-testid="bandwidth-result"]')).toContainText(/\d+/);
    });
  });

  test('Node health monitoring and alerts', async () => {
    await test.step('Access health monitoring', async () => {
      await page.goto('/betanet/health');
      await expect(page.locator('[data-testid="health-dashboard"]')).toBeVisible();
    });

    await test.step('View node health status', async () => {
      const healthGrid = page.locator('[data-testid="health-grid"]');
      await expect(healthGrid).toBeVisible();

      // Check health indicators
      const nodes = page.locator('[data-testid="node-health-card"]');
      const nodeCount = await nodes.count();
      expect(nodeCount).toBeGreaterThan(0);

      // Verify health metrics
      const firstNode = nodes.first();
      await expect(firstNode.locator('[data-testid="health-score"]')).toBeVisible();
      await expect(firstNode.locator('[data-testid="uptime"]')).toBeVisible();
      await expect(firstNode.locator('[data-testid="response-time"]')).toBeVisible();
    });

    await test.step('Configure health alerts', async () => {
      await page.click('[data-testid="alerts-tab"]');
      await page.click('[data-testid="create-alert-button"]');

      await page.fill('[data-testid="alert-name-input"]', 'High Latency Alert');
      await page.selectOption('[data-testid="metric-select"]', 'latency');
      await page.selectOption('[data-testid="condition-select"]', 'greater_than');
      await page.fill('[data-testid="threshold-input"]', '100');
      await page.selectOption('[data-testid="severity-select"]', 'warning');

      await page.click('[data-testid="save-alert-button"]');

      await expect(page.locator('[data-testid="alert-item"]', { hasText: 'High Latency Alert' })).toBeVisible();
    });

    await test.step('View alert history', async () => {
      await page.click('[data-testid="alert-history-tab"]');

      const history = page.locator('[data-testid="alert-history-table"]');
      await expect(history).toBeVisible();

      // Filter by severity
      await page.selectOption('[data-testid="severity-filter"]', 'warning');

      const rows = page.locator('[data-testid="alert-row"]');
      const count = await rows.count();
      if (count > 0) {
        await expect(rows.first().locator('[data-testid="alert-severity"]')).toContainText('Warning');
      }
    });
  });

  test('Network topology analysis', async () => {
    await test.step('Load topology analyzer', async () => {
      await page.goto('/betanet/topology');
      await expect(page.locator('[data-testid="topology-analyzer"]')).toBeVisible();
    });

    await test.step('Analyze network structure', async () => {
      await page.click('[data-testid="analyze-topology-button"]');

      // Wait for analysis
      await expect(page.locator('[data-testid="analysis-status"]')).toHaveText('Analyzing...', { timeout: 2000 });
      await expect(page.locator('[data-testid="analysis-status"]')).toHaveText('Complete', { timeout: 20000 });

      // Verify analysis results
      const results = page.locator('[data-testid="topology-analysis"]');
      await expect(results).toBeVisible();

      await expect(results.locator('[data-testid="node-centrality"]')).toBeVisible();
      await expect(results.locator('[data-testid="clustering-coefficient"]')).toBeVisible();
      await expect(results.locator('[data-testid="network-diameter"]')).toBeVisible();
      await expect(results.locator('[data-testid="avg-path-length"]')).toBeVisible();
    });

    await test.step('Identify critical nodes', async () => {
      await page.click('[data-testid="critical-nodes-tab"]');

      const criticalNodes = page.locator('[data-testid="critical-node-item"]');
      const count = await criticalNodes.count();
      expect(count).toBeGreaterThan(0);

      // Check node importance score
      const firstCritical = criticalNodes.first();
      await expect(firstCritical.locator('[data-testid="importance-score"]')).toContainText(/\d+/);
      await expect(firstCritical.locator('[data-testid="connection-count"]')).toContainText(/\d+/);
    });

    await test.step('Simulate node failure', async () => {
      await page.click('[data-testid="simulation-tab"]');

      const nodeSelect = page.locator('[data-testid="simulate-node-select"]');
      await nodeSelect.selectOption({ index: 1 });

      await page.click('[data-testid="simulate-failure-button"]');

      // View simulation results
      const impactAnalysis = page.locator('[data-testid="impact-analysis"]');
      await expect(impactAnalysis).toBeVisible();

      await expect(impactAnalysis.locator('[data-testid="affected-nodes"]')).toContainText(/\d+/);
      await expect(impactAnalysis.locator('[data-testid="isolated-nodes"]')).toContainText(/\d+/);
      await expect(impactAnalysis.locator('[data-testid="path-impact"]')).toBeVisible();
    });
  });

  test('Performance benchmarking', async () => {
    await test.step('Navigate to benchmarks', async () => {
      await page.goto('/betanet/benchmarks');
      await expect(page.locator('[data-testid="benchmark-dashboard"]')).toBeVisible();
    });

    await test.step('Run network benchmark', async () => {
      await page.click('[data-testid="run-benchmark-button"]');

      await page.selectOption('[data-testid="benchmark-type-select"]', 'throughput');
      await page.fill('[data-testid="duration-input"]', '30');
      await page.fill('[data-testid="packet-size-input"]', '1500');

      await page.click('[data-testid="start-benchmark-button"]');

      // Monitor benchmark progress
      const progress = page.locator('[data-testid="benchmark-progress"]');
      await expect(progress).toBeVisible();

      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Running', { timeout: 5000 });
      await expect(page.locator('[data-testid="benchmark-status"]')).toHaveText('Complete', { timeout: 60000 });
    });

    await test.step('View benchmark results', async () => {
      const results = page.locator('[data-testid="benchmark-results"]');
      await expect(results).toBeVisible();

      await expect(results.locator('[data-testid="avg-throughput"]')).toContainText(/\d+/);
      await expect(results.locator('[data-testid="peak-throughput"]')).toContainText(/\d+/);
      await expect(results.locator('[data-testid="packet-loss"]')).toContainText(/\d+/);

      // Verify results chart
      await expect(page.locator('[data-testid="benchmark-chart"]')).toBeVisible();
    });

    await test.step('Compare benchmark history', async () => {
      await page.click('[data-testid="history-tab"]');

      const historyTable = page.locator('[data-testid="benchmark-history"]');
      await expect(historyTable).toBeVisible();

      const rows = page.locator('[data-testid="benchmark-row"]');
      const count = await rows.count();
      expect(count).toBeGreaterThan(0);

      // Select multiple benchmarks for comparison
      await page.check('[data-testid="benchmark-checkbox"]:nth-child(1)');
      await page.check('[data-testid="benchmark-checkbox"]:nth-child(2)');

      await page.click('[data-testid="compare-button"]');

      const comparison = page.locator('[data-testid="benchmark-comparison"]');
      await expect(comparison).toBeVisible();
      await expect(comparison.locator('[data-testid="comparison-chart"]')).toBeVisible();
    });
  });
});