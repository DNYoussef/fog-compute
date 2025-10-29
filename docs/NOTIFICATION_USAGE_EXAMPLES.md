# Notification System - Real Usage Examples

## Common Integration Patterns

This document shows real-world examples of how to integrate notifications into your components.

## Table of Contents

1. [Resource Management](#resource-management)
2. [Node Deployment](#node-deployment)
3. [Configuration Changes](#configuration-changes)
4. [API Operations](#api-operations)
5. [Form Validation](#form-validation)
6. [Batch Operations](#batch-operations)

---

## Resource Management

### Example: Update Resource Limits

```typescript
'use client';

import { useState } from 'react';
import { showSuccess, showError, showPromise } from '@/components/SuccessNotification';

export function ResourceLimitsForm() {
  const [cpu, setCpu] = useState(4);
  const [memory, setMemory] = useState(8);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await showPromise(
        fetch('/api/resources/limits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cpu, memory }),
        }).then(res => {
          if (!res.ok) throw new Error('Failed to update');
          return res.json();
        }),
        {
          loading: 'Updating resource limits...',
          success: `Resource limits updated: CPU ${cpu} cores, Memory ${memory}GB`,
          error: (err) => `Update failed: ${err.message}`,
        }
      );
    } catch (error) {
      // Error already shown by showPromise
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label>CPU Cores</label>
        <input
          type="number"
          value={cpu}
          onChange={(e) => setCpu(Number(e.target.value))}
          min={1}
          max={64}
        />
      </div>
      <div>
        <label>Memory (GB)</label>
        <input
          type="number"
          value={memory}
          onChange={(e) => setMemory(Number(e.target.value))}
          min={1}
          max={256}
        />
      </div>
      <button type="submit">Update Limits</button>
    </form>
  );
}
```

---

## Node Deployment

### Example: Deploy Node with Loading State

```typescript
'use client';

import { useState } from 'react';
import { showLoading, dismissNotification, showSuccess, showError } from '@/components/SuccessNotification';

export function NodeDeploymentPanel() {
  const [isDeploying, setIsDeploying] = useState(false);

  const deployNode = async (nodeId: string) => {
    setIsDeploying(true);
    const loadingId = showLoading('Deploying node to network...');

    try {
      const response = await fetch(`/api/nodes/${nodeId}/deploy`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      dismissNotification(loadingId);
      showSuccess(`Node ${data.nodeName} deployed successfully to ${data.region}`);
    } catch (error) {
      dismissNotification(loadingId);
      showError(`Deployment failed: ${error.message}`);
    } finally {
      setIsDeploying(false);
    }
  };

  return (
    <div>
      <button
        onClick={() => deployNode('node-123')}
        disabled={isDeploying}
        className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
      >
        {isDeploying ? 'Deploying...' : 'Deploy Node'}
      </button>
    </div>
  );
}
```

### Example: Deploy Multiple Nodes

```typescript
'use client';

import { showSuccess, showError, showInfo } from '@/components/SuccessNotification';

export function BulkNodeDeployment() {
  const deployMultipleNodes = async (nodeIds: string[]) => {
    showInfo(`Starting deployment of ${nodeIds.length} nodes...`);

    let successCount = 0;
    let failureCount = 0;

    for (const nodeId of nodeIds) {
      try {
        await fetch(`/api/nodes/${nodeId}/deploy`, { method: 'POST' });
        successCount++;
      } catch (error) {
        failureCount++;
      }
    }

    if (failureCount === 0) {
      showSuccess(`Successfully deployed ${successCount} nodes`);
    } else if (successCount === 0) {
      showError(`Failed to deploy all ${failureCount} nodes`);
    } else {
      showWarning(`Deployed ${successCount} nodes, ${failureCount} failed`);
    }
  };

  return (
    <button onClick={() => deployMultipleNodes(['node-1', 'node-2', 'node-3'])}>
      Deploy All Nodes
    </button>
  );
}
```

---

## Configuration Changes

### Example: Save Configuration

```typescript
'use client';

import { showSuccess, showError } from '@/components/SuccessNotification';

export function ConfigurationPanel() {
  const [config, setConfig] = useState({
    autoScaling: false,
    maxNodes: 10,
    region: 'us-west-1',
  });

  const saveConfiguration = async () => {
    try {
      const response = await fetch('/api/configuration', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error('Failed to save configuration');
      }

      showSuccess('Configuration saved successfully');
    } catch (error) {
      showError(`Failed to save: ${error.message}`);
    }
  };

  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={config.autoScaling}
          onChange={(e) => setConfig({ ...config, autoScaling: e.target.checked })}
        />
        Enable Auto-Scaling
      </label>

      <button onClick={saveConfiguration}>
        Save Configuration
      </button>
    </div>
  );
}
```

---

## API Operations

### Example: API Key Management

```typescript
'use client';

import { useState } from 'react';
import { showSuccess, showWarning, showPromise } from '@/components/SuccessNotification';

export function APIKeyManager() {
  const [apiKey, setApiKey] = useState('');

  const regenerateAPIKey = async () => {
    // Show warning before regenerating
    showWarning('Regenerating API key - existing key will be invalidated');

    await showPromise(
      fetch('/api/auth/regenerate-key', { method: 'POST' })
        .then(res => res.json()),
      {
        loading: 'Regenerating API key...',
        success: (data) => {
          setApiKey(data.key);
          return 'API key regenerated - please update your clients';
        },
        error: (err) => `Failed to regenerate key: ${err.message}`,
      }
    );
  };

  const copyAPIKey = () => {
    navigator.clipboard.writeText(apiKey);
    showSuccess('API key copied to clipboard');
  };

  return (
    <div>
      <div className="flex gap-2">
        <input type="text" value={apiKey} readOnly />
        <button onClick={copyAPIKey}>Copy</button>
        <button onClick={regenerateAPIKey}>Regenerate</button>
      </div>
    </div>
  );
}
```

---

## Form Validation

### Example: Form with Client-side Validation

```typescript
'use client';

import { useState } from 'react';
import { showSuccess, showError, showWarning } from '@/components/SuccessNotification';

export function NodeRegistrationForm() {
  const [nodeName, setNodeName] = useState('');
  const [nodeIP, setNodeIP] = useState('');

  const validateForm = () => {
    if (!nodeName.trim()) {
      showWarning('Please enter a node name');
      return false;
    }

    if (!nodeIP.match(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/)) {
      showWarning('Please enter a valid IP address');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      const response = await fetch('/api/nodes/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nodeName, ip: nodeIP }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message);
      }

      showSuccess(`Node "${nodeName}" registered successfully`);
      setNodeName('');
      setNodeIP('');
    } catch (error) {
      showError(`Registration failed: ${error.message}`);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={nodeName}
        onChange={(e) => setNodeName(e.target.value)}
        placeholder="Node name"
      />
      <input
        type="text"
        value={nodeIP}
        onChange={(e) => setNodeIP(e.target.value)}
        placeholder="IP address"
      />
      <button type="submit">Register Node</button>
    </form>
  );
}
```

---

## Batch Operations

### Example: Batch Delete with Confirmation

```typescript
'use client';

import { useState } from 'react';
import { showSuccess, showError, showWarning, showPromise } from '@/components/SuccessNotification';

export function BatchDeletePanel() {
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);

  const deleteSelectedNodes = async () => {
    if (selectedNodes.length === 0) {
      showWarning('No nodes selected');
      return;
    }

    // Show warning for dangerous operation
    showWarning(`Deleting ${selectedNodes.length} nodes - this cannot be undone`);

    await showPromise(
      fetch('/api/nodes/batch-delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodeIds: selectedNodes }),
      }).then(res => {
        if (!res.ok) throw new Error('Batch delete failed');
        return res.json();
      }),
      {
        loading: `Deleting ${selectedNodes.length} nodes...`,
        success: (data) => {
          setSelectedNodes([]);
          return `Successfully deleted ${data.deletedCount} nodes`;
        },
        error: (err) => `Deletion failed: ${err.message}`,
      }
    );
  };

  return (
    <div>
      <button
        onClick={deleteSelectedNodes}
        className="px-4 py-2 bg-red-600 text-white rounded"
      >
        Delete Selected ({selectedNodes.length})
      </button>
    </div>
  );
}
```

---

## Server Actions (Next.js App Router)

### Example: Server Action with Client Notification

```typescript
// app/actions/nodes.ts
'use server';

export async function updateNodeStatus(nodeId: string, status: string) {
  try {
    // Perform database update
    await db.nodes.update({
      where: { id: nodeId },
      data: { status },
    });

    return {
      success: true,
      message: `Node status updated to ${status}`,
    };
  } catch (error) {
    return {
      success: false,
      message: `Failed to update status: ${error.message}`,
    };
  }
}
```

```typescript
// components/NodeStatusToggle.tsx
'use client';

import { updateNodeStatus } from '@/app/actions/nodes';
import { showSuccess, showError } from '@/components/SuccessNotification';

export function NodeStatusToggle({ nodeId }: { nodeId: string }) {
  const handleStatusChange = async (newStatus: string) => {
    const result = await updateNodeStatus(nodeId, newStatus);

    if (result.success) {
      showSuccess(result.message);
    } else {
      showError(result.message);
    }
  };

  return (
    <select onChange={(e) => handleStatusChange(e.target.value)}>
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
      <option value="maintenance">Maintenance</option>
    </select>
  );
}
```

---

## SWR Integration

### Example: Mutation with Notification

```typescript
'use client';

import useSWR, { mutate } from 'swr';
import { showSuccess, showError } from '@/components/SuccessNotification';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export function NodeList() {
  const { data: nodes, error } = useSWR('/api/nodes', fetcher);

  const restartNode = async (nodeId: string) => {
    try {
      await fetch(`/api/nodes/${nodeId}/restart`, { method: 'POST' });

      // Revalidate data
      await mutate('/api/nodes');

      showSuccess('Node restarted successfully');
    } catch (error) {
      showError(`Failed to restart node: ${error.message}`);
    }
  };

  if (error) {
    showError('Failed to load nodes');
    return <div>Error loading nodes</div>;
  }

  if (!nodes) return <div>Loading...</div>;

  return (
    <ul>
      {nodes.map((node) => (
        <li key={node.id}>
          {node.name}
          <button onClick={() => restartNode(node.id)}>Restart</button>
        </li>
      ))}
    </ul>
  );
}
```

---

## WebSocket Updates

### Example: Real-time Notifications

```typescript
'use client';

import { useEffect } from 'react';
import { showInfo, showWarning, showError } from '@/components/SuccessNotification';

export function RealtimeMonitor() {
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:3000/api/events');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'node_online':
          showInfo(`Node ${data.nodeName} is now online`);
          break;
        case 'node_offline':
          showWarning(`Node ${data.nodeName} went offline`);
          break;
        case 'node_error':
          showError(`Node ${data.nodeName}: ${data.error}`);
          break;
      }
    };

    return () => ws.close();
  }, []);

  return <div>Monitoring real-time events...</div>;
}
```

---

## Tips & Best Practices

1. **Use appropriate notification types**
   - Success: Confirmed actions
   - Error: Failed operations requiring user attention
   - Warning: Potential issues or dangerous operations
   - Info: Neutral information or status updates

2. **Keep messages concise and actionable**
   ```typescript
   // Good
   showSuccess('Settings saved');

   // Better
   showSuccess('Settings saved - changes will apply in 30 seconds');
   ```

3. **Handle errors gracefully**
   ```typescript
   try {
     await operation();
     showSuccess('Operation completed');
   } catch (error) {
     // Provide context
     showError(`Operation failed: ${error.message}`);
   }
   ```

4. **Use promise-based notifications for async operations**
   ```typescript
   // Automatic loading/success/error handling
   showPromise(asyncOperation(), {
     loading: 'Processing...',
     success: 'Done!',
     error: (err) => `Failed: ${err.message}`,
   });
   ```

5. **Don't spam notifications**
   ```typescript
   // Use unique IDs to prevent duplicates
   showSuccess('Autosave complete', { id: 'autosave' });
   ```

6. **Test notification behavior**
   ```typescript
   // E2E test
   await page.click('[data-testid="save-button"]');
   await page.waitForSelector('[data-testid="success-notification"]');
   expect(await page.textContent('[data-testid="notification-message"]'))
     .toContain('Settings saved');
   ```
