import { test, expect, Page } from '@playwright/test';

/**
 * Complete Control Panel Workflow E2E Tests
 * Tests the entire control panel functionality from initialization to operations
 */

test.describe('Complete Control Panel Workflow', () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
  });

  test.afterAll(async () => {
    await page.close();
  });

  test('Full control panel workflow: initialization -> node management -> monitoring', async () => {
    // Step 1: Initialize control panel
    await test.step('Load and initialize control panel', async () => {
      await page.goto('/');
      await expect(page).toHaveTitle(/Fog Compute/);

      const controlPanel = page.locator('[data-testid="control-panel"]');
      await expect(controlPanel).toBeVisible({ timeout: 10000 });
    });

    // Step 2: Check system status
    await test.step('Verify system status dashboard', async () => {
      const statusSection = page.locator('[data-testid="system-status"]');
      await expect(statusSection).toBeVisible();

      await expect(page.locator('[data-testid="node-count"]')).toContainText(/\d+/);
      await expect(page.locator('[data-testid="network-status"]')).toContainText(/Online|Active/i);
      await expect(page.locator('[data-testid="cpu-usage"]')).toBeVisible();
      await expect(page.locator('[data-testid="memory-usage"]')).toBeVisible();
    });

    // Step 3: Node management
    let nodeId: string;
    await test.step('Create and configure fog node', async () => {
      await page.click('[data-testid="nodes-tab"]');
      await page.click('[data-testid="add-node-button"]');

      // Fill node configuration
      await page.fill('[data-testid="node-name-input"]', 'E2E-Test-Node');
      await page.fill('[data-testid="node-ip-input"]', '192.168.1.100');
      await page.selectOption('[data-testid="node-type-select"]', 'compute');
      await page.fill('[data-testid="node-capacity-input"]', '1000');

      // Advanced configuration
      await page.click('[data-testid="advanced-config-toggle"]');
      await page.fill('[data-testid="max-connections-input"]', '50');
      await page.check('[data-testid="enable-monitoring-checkbox"]');

      await page.click('[data-testid="create-node-button"]');

      // Verify node creation
      await expect(page.locator('[data-testid="success-notification"]')).toBeVisible();

      const nodeCard = page.locator('[data-testid="node-card"]', { hasText: 'E2E-Test-Node' });
      await expect(nodeCard).toBeVisible();
      nodeId = await nodeCard.getAttribute('data-node-id') || '';
      expect(nodeId).toBeTruthy();
    });

    // Step 4: Monitor node status
    await test.step('Monitor node initialization and status', async () => {
      const nodeDetails = page.locator(`[data-node-id="${nodeId}"]`);
      await nodeDetails.click();

      const detailsPanel = page.locator('[data-testid="node-details-panel"]');
      await expect(detailsPanel).toBeVisible();

      // Wait for node to be online
      await expect(page.locator('[data-testid="node-status-badge"]')).toHaveText('Online', { timeout: 30000 });

      // Verify metrics
      await expect(page.locator('[data-testid="node-cpu-metric"]')).toBeVisible();
      await expect(page.locator('[data-testid="node-memory-metric"]')).toBeVisible();
      await expect(page.locator('[data-testid="node-network-metric"]')).toBeVisible();
    });

    // Step 5: Network configuration
    await test.step('Configure network settings', async () => {
      await page.click('[data-testid="network-tab"]');

      const networkConfig = page.locator('[data-testid="network-config"]');
      await expect(networkConfig).toBeVisible();

      // Update network settings
      await page.fill('[data-testid="bandwidth-limit-input"]', '1000');
      await page.selectOption('[data-testid="protocol-select"]', 'tcp');
      await page.check('[data-testid="enable-encryption-checkbox"]');

      await page.click('[data-testid="apply-network-config-button"]');

      await expect(page.locator('[data-testid="success-notification"]')).toContainText('Network settings updated');
    });

    // Step 6: Task deployment
    await test.step('Deploy and execute fog task', async () => {
      await page.click('[data-testid="tasks-tab"]');
      await page.click('[data-testid="deploy-task-button"]');

      // Configure task
      await page.fill('[data-testid="task-name-input"]', 'E2E-Test-Task');
      await page.selectOption('[data-testid="task-type-select"]', 'data_processing');
      await page.fill('[data-testid="task-config-input"]', JSON.stringify({
        input: 'sample_data',
        processing_type: 'batch'
      }));

      // Assign to node
      await page.selectOption('[data-testid="target-node-select"]', nodeId);

      await page.click('[data-testid="deploy-button"]');

      // Monitor deployment
      await expect(page.locator('[data-testid="deployment-status"]')).toHaveText('Deploying', { timeout: 5000 });
      await expect(page.locator('[data-testid="deployment-status"]')).toHaveText('Running', { timeout: 30000 });
    });

    // Step 7: Real-time monitoring
    await test.step('Monitor task execution in real-time', async () => {
      const taskMonitor = page.locator('[data-testid="task-monitor"]');
      await expect(taskMonitor).toBeVisible();

      // Verify real-time metrics
      await expect(page.locator('[data-testid="task-progress"]')).toBeVisible();
      await expect(page.locator('[data-testid="resource-usage"]')).toBeVisible();

      // Wait for completion
      await expect(page.locator('[data-testid="task-status"]')).toHaveText(/Completed|Success/i, { timeout: 60000 });
    });

    // Step 8: View logs and analytics
    await test.step('Access logs and analytics', async () => {
      await page.click('[data-testid="logs-tab"]');

      const logsPanel = page.locator('[data-testid="logs-panel"]');
      await expect(logsPanel).toBeVisible();

      // Filter logs
      await page.selectOption('[data-testid="log-level-filter"]', 'info');
      await page.fill('[data-testid="log-search-input"]', 'E2E-Test');

      const logEntries = page.locator('[data-testid="log-entry"]');
      await expect(logEntries).toHaveCount({ min: 1 });

      // View analytics
      await page.click('[data-testid="analytics-tab"]');
      await expect(page.locator('[data-testid="analytics-dashboard"]')).toBeVisible();
      await expect(page.locator('[data-testid="performance-chart"]')).toBeVisible();
    });

    // Step 9: Cleanup
    await test.step('Cleanup: remove test node', async () => {
      await page.click('[data-testid="nodes-tab"]');
      await page.click(`[data-node-id="${nodeId}"] [data-testid="node-menu-button"]`);
      await page.click('[data-testid="delete-node-option"]');

      // Confirm deletion
      await page.click('[data-testid="confirm-delete-button"]');

      await expect(page.locator('[data-testid="success-notification"]')).toContainText('Node deleted');
      await expect(page.locator(`[data-node-id="${nodeId}"]`)).not.toBeVisible();
    });
  });

  test('Edge deployment and orchestration workflow', async () => {
    await test.step('Navigate to edge deployment', async () => {
      await page.goto('/edge');
      await expect(page.locator('h1')).toContainText(/Edge|Deployment/i);
    });

    let deploymentId: string;
    await test.step('Create edge deployment', async () => {
      await page.click('[data-testid="create-deployment-button"]');

      await page.fill('[data-testid="deployment-name-input"]', 'E2E-Edge-Deployment');
      await page.selectOption('[data-testid="deployment-strategy-select"]', 'distributed');
      await page.fill('[data-testid="replica-count-input"]', '3');

      // Container configuration
      await page.fill('[data-testid="container-image-input"]', 'nginx:latest');
      await page.fill('[data-testid="container-port-input"]', '80');

      await page.click('[data-testid="deploy-button"]');

      const deploymentCard = page.locator('[data-testid="deployment-card"]', { hasText: 'E2E-Edge-Deployment' });
      await expect(deploymentCard).toBeVisible();
      deploymentId = await deploymentCard.getAttribute('data-deployment-id') || '';
    });

    await test.step('Monitor deployment rollout', async () => {
      const deploymentStatus = page.locator(`[data-deployment-id="${deploymentId}"] [data-testid="deployment-status"]`);
      await expect(deploymentStatus).toHaveText(/Deploying|Rolling out/i, { timeout: 5000 });

      // Wait for ready state
      await expect(deploymentStatus).toHaveText('Ready', { timeout: 120000 });

      // Verify replicas
      const replicaCount = page.locator(`[data-deployment-id="${deploymentId}"] [data-testid="replica-count"]`);
      await expect(replicaCount).toHaveText('3/3');
    });

    await test.step('Scale deployment', async () => {
      await page.click(`[data-deployment-id="${deploymentId}"] [data-testid="scale-button"]`);
      await page.fill('[data-testid="scale-replicas-input"]', '5');
      await page.click('[data-testid="confirm-scale-button"]');

      // Verify scaling
      const replicaCount = page.locator(`[data-deployment-id="${deploymentId}"] [data-testid="replica-count"]`);
      await expect(replicaCount).toHaveText('5/5', { timeout: 60000 });
    });

    await test.step('Update deployment configuration', async () => {
      await page.click(`[data-deployment-id="${deploymentId}"] [data-testid="update-button"]`);

      await page.fill('[data-testid="container-image-input"]', 'nginx:alpine');
      await page.selectOption('[data-testid="update-strategy-select"]', 'rolling');

      await page.click('[data-testid="apply-update-button"]');

      // Monitor rolling update
      await expect(page.locator('[data-testid="update-progress"]')).toBeVisible();
      await expect(page.locator('[data-testid="deployment-status"]')).toHaveText('Ready', { timeout: 120000 });
    });
  });

  test('Resource management and optimization workflow', async () => {
    await test.step('Access resource dashboard', async () => {
      await page.goto('/resources');
      await expect(page.locator('[data-testid="resource-dashboard"]')).toBeVisible();
    });

    await test.step('Analyze resource utilization', async () => {
      const utilizationChart = page.locator('[data-testid="utilization-chart"]');
      await expect(utilizationChart).toBeVisible();

      // Check resource breakdown
      await expect(page.locator('[data-testid="cpu-allocation"]')).toBeVisible();
      await expect(page.locator('[data-testid="memory-allocation"]')).toBeVisible();
      await expect(page.locator('[data-testid="storage-allocation"]')).toBeVisible();
      await expect(page.locator('[data-testid="network-allocation"]')).toBeVisible();
    });

    await test.step('Configure resource limits', async () => {
      await page.click('[data-testid="resource-limits-tab"]');

      // Set CPU limits
      await page.fill('[data-testid="cpu-limit-input"]', '80');
      await page.fill('[data-testid="cpu-reserve-input"]', '20');

      // Set memory limits
      await page.fill('[data-testid="memory-limit-input"]', '8192');
      await page.fill('[data-testid="memory-reserve-input"]', '2048');

      await page.click('[data-testid="apply-limits-button"]');

      await expect(page.locator('[data-testid="success-notification"]')).toContainText('Resource limits updated');
    });

    await test.step('Enable auto-scaling', async () => {
      await page.click('[data-testid="auto-scaling-tab"]');

      await page.check('[data-testid="enable-auto-scaling-checkbox"]');
      await page.fill('[data-testid="scale-up-threshold-input"]', '80');
      await page.fill('[data-testid="scale-down-threshold-input"]', '30');
      await page.fill('[data-testid="min-instances-input"]', '2');
      await page.fill('[data-testid="max-instances-input"]', '10');

      await page.click('[data-testid="save-auto-scaling-button"]');

      await expect(page.locator('[data-testid="auto-scaling-status"]')).toHaveText('Enabled');
    });
  });

  test('Security and access control workflow', async () => {
    await test.step('Navigate to security settings', async () => {
      await page.goto('/security');
      await expect(page.locator('[data-testid="security-dashboard"]')).toBeVisible();
    });

    await test.step('Configure network policies', async () => {
      await page.click('[data-testid="network-policies-tab"]');
      await page.click('[data-testid="add-policy-button"]');

      await page.fill('[data-testid="policy-name-input"]', 'E2E-Test-Policy');
      await page.selectOption('[data-testid="policy-type-select"]', 'ingress');
      await page.fill('[data-testid="allowed-ips-input"]', '10.0.0.0/8');
      await page.fill('[data-testid="allowed-ports-input"]', '80,443');

      await page.click('[data-testid="create-policy-button"]');

      await expect(page.locator('[data-testid="policy-item"]', { hasText: 'E2E-Test-Policy' })).toBeVisible();
    });

    await test.step('Configure TLS/SSL', async () => {
      await page.click('[data-testid="tls-config-tab"]');

      await page.check('[data-testid="enable-tls-checkbox"]');
      await page.selectOption('[data-testid="tls-version-select"]', 'TLS1.3');
      await page.fill('[data-testid="certificate-path-input"]', '/etc/ssl/certs/cert.pem');
      await page.fill('[data-testid="key-path-input"]', '/etc/ssl/private/key.pem');

      await page.click('[data-testid="apply-tls-config-button"]');

      await expect(page.locator('[data-testid="tls-status"]')).toHaveText('Enabled');
    });

    await test.step('Set up access controls', async () => {
      await page.click('[data-testid="access-control-tab"]');
      await page.click('[data-testid="add-role-button"]');

      await page.fill('[data-testid="role-name-input"]', 'E2E-Test-Role');
      await page.check('[data-testid="read-permission-checkbox"]');
      await page.check('[data-testid="write-permission-checkbox"]');

      await page.click('[data-testid="create-role-button"]');

      await expect(page.locator('[data-testid="role-item"]', { hasText: 'E2E-Test-Role' })).toBeVisible();
    });
  });
});