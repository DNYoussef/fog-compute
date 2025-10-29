# Notification System Integration Guide

## Overview

The Fog Compute Control Panel uses a comprehensive notification system built on `react-hot-toast` to provide user feedback for all operations. This guide explains how to integrate notifications into your components.

## Architecture

### Components

1. **NotificationToaster** (`components/SuccessNotification.tsx`)
   - Root toast container with custom styling
   - Includes test IDs for E2E testing
   - Already integrated in `app/layout.tsx`

2. **Helper Functions** (`components/SuccessNotification.tsx`)
   - `showSuccess()` - Success notifications
   - `showError()` - Error notifications
   - `showWarning()` - Warning notifications
   - `showInfo()` - Info notifications
   - `showLoading()` - Loading notifications
   - `showPromise()` - Promise-based notifications
   - `dismissNotification()` - Dismiss notifications

## Basic Usage

### Import the helpers

```typescript
import { showSuccess, showError, showWarning, showInfo } from '@/components/SuccessNotification';
```

### Show notifications

```typescript
// Success notification
showSuccess('Resource limits updated successfully');

// Error notification
showError('Failed to deploy node: Connection timeout');

// Warning notification
showWarning('Node performance degraded - check resources');

// Info notification
showInfo('Node discovery in progress...');
```

## Advanced Usage

### Loading States

For operations with loading states:

```typescript
import { showLoading, dismissNotification, showSuccess } from '@/components/SuccessNotification';

// Start loading
const loadingId = showLoading('Deploying node...');

try {
  await deployNode(nodeId);

  // Dismiss loading and show success
  dismissNotification(loadingId);
  showSuccess('Node deployed successfully');
} catch (error) {
  // Dismiss loading and show error
  dismissNotification(loadingId);
  showError(`Deployment failed: ${error.message}`);
}
```

### Promise-based Notifications

For automatic loading/success/error handling:

```typescript
import { showPromise } from '@/components/SuccessNotification';

showPromise(
  deployNode(nodeId),
  {
    loading: 'Deploying node...',
    success: 'Node deployed successfully',
    error: (err) => `Deployment failed: ${err.message}`
  }
);
```

### Custom Duration

```typescript
// Stay for 10 seconds
showSuccess('Important message', { duration: 10000 });

// Stay for 2 seconds
showInfo('Quick message', { duration: 2000 });

// Stay forever (until dismissed)
showSuccess('Persistent message', { duration: Infinity });
```

### Custom Icons

```typescript
showSuccess('Launch successful', { icon: '🚀' });
showWarning('Server maintenance', { icon: '🔧' });
```

### Custom ID (for deduplication)

```typescript
// Only one notification with this ID will be shown
showSuccess('Update available', { id: 'update-notification' });
```

## Integration Examples

### Form Submission

```typescript
'use client';

import { showSuccess, showError } from '@/components/SuccessNotification';

export function SettingsForm() {
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await updateSettings(formData);
      showSuccess('Settings saved successfully');
    } catch (error) {
      showError(`Failed to save settings: ${error.message}`);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* form fields */}
    </form>
  );
}
```

### API Calls

```typescript
'use client';

import { showPromise } from '@/components/SuccessNotification';

export function ResourceManager() {
  const updateLimits = async (limits: ResourceLimits) => {
    await showPromise(
      api.updateResourceLimits(limits),
      {
        loading: 'Updating resource limits...',
        success: (data) => `Resource limits updated: CPU ${data.cpu} cores, Memory ${data.memory}GB`,
        error: (err) => `Update failed: ${err.message}`
      }
    );
  };

  return (
    <button onClick={() => updateLimits({ cpu: 8, memory: 16 })}>
      Update Limits
    </button>
  );
}
```

### Confirmation Actions

```typescript
'use client';

import { showSuccess, showWarning } from '@/components/SuccessNotification';

export function NodeManager() {
  const deleteNode = async (nodeId: string) => {
    // Show warning first
    showWarning('Deleting node - this action cannot be undone');

    try {
      await api.deleteNode(nodeId);
      showSuccess('Node deleted successfully');
    } catch (error) {
      showError(`Failed to delete node: ${error.message}`);
    }
  };

  return (
    <button onClick={() => deleteNode('node-123')}>
      Delete Node
    </button>
  );
}
```

### Server Actions (Next.js)

```typescript
'use server';

import { showSuccess, showError } from '@/components/SuccessNotification';

export async function deployNodeAction(nodeId: string) {
  try {
    await deployNodeToNetwork(nodeId);
    return { success: true, message: 'Node deployed successfully' };
  } catch (error) {
    return { success: false, message: `Deployment failed: ${error.message}` };
  }
}

// In client component:
'use client';

import { deployNodeAction } from '@/actions/nodes';
import { showSuccess, showError } from '@/components/SuccessNotification';

export function DeployButton({ nodeId }: { nodeId: string }) {
  const handleDeploy = async () => {
    const result = await deployNodeAction(nodeId);

    if (result.success) {
      showSuccess(result.message);
    } else {
      showError(result.message);
    }
  };

  return <button onClick={handleDeploy}>Deploy</button>;
}
```

## E2E Testing

The notification system includes test IDs for E2E testing:

```typescript
// Playwright test example
test('shows success notification on resource update', async ({ page }) => {
  await page.goto('/resources');
  await page.fill('[name="cpu"]', '8');
  await page.fill('[name="memory"]', '16');
  await page.click('button[type="submit"]');

  // Wait for success notification
  await page.waitForSelector('[data-testid="success-notification"]');

  // Verify message
  const message = await page.textContent('[data-testid="notification-message"]');
  expect(message).toContain('Resource limits updated');
});

test('shows error notification on failed deployment', async ({ page }) => {
  await page.goto('/nodes');
  await page.click('button[data-testid="deploy-button"]');

  // Wait for error notification
  await page.waitForSelector('[data-testid="error-notification"]');

  // Verify error message
  const message = await page.textContent('[data-testid="notification-message"]');
  expect(message).toContain('Deployment failed');
});
```

### Available Test IDs

- `success-notification` - Success toast
- `error-notification` - Error toast
- `loading-notification` - Loading toast
- `notification` - Generic notification
- `notification-message` - Message content
- `notification-close` - Close button

## Styling Customization

The notifications are styled to match the Fog Compute design system. To customize:

### Global Styles (in layout.tsx)

```typescript
<Toaster
  position="top-right"
  toastOptions={{
    duration: 5000,
    style: {
      background: '#0a0e27',
      color: '#fff',
      border: '1px solid rgba(255, 255, 255, 0.1)',
    },
    success: {
      iconTheme: {
        primary: '#10b981',
        secondary: '#fff',
      },
    },
    error: {
      iconTheme: {
        primary: '#ef4444',
        secondary: '#fff',
      },
    },
  }}
/>
```

### Per-notification Styles

```typescript
import { toast } from '@/components/SuccessNotification';

toast.success('Custom styled', {
  style: {
    background: 'linear-gradient(to right, #667eea, #764ba2)',
    color: '#fff',
  },
});
```

## Migration from Old Pattern

If you have existing notification code:

### Before (custom implementation)

```typescript
setNotification({ type: 'success', message: 'Saved' });
setTimeout(() => setNotification(null), 5000);
```

### After (new notification system)

```typescript
import { showSuccess } from '@/components/SuccessNotification';
showSuccess('Saved');
```

## Best Practices

1. **Use appropriate notification types**
   - Success: User actions completed successfully
   - Error: Operations failed, user needs to act
   - Warning: Potential issues, not blocking
   - Info: Neutral information, FYI messages

2. **Keep messages concise**
   - Clear, actionable messages
   - Include context when needed
   - Avoid technical jargon

3. **Use promise-based notifications for async operations**
   - Automatic loading/success/error states
   - Better UX for long-running operations

4. **Don't spam notifications**
   - Use unique IDs to prevent duplicates
   - Batch related operations
   - Consider using loading states

5. **Test notification behavior**
   - Include test IDs in E2E tests
   - Verify messages and timing
   - Test error scenarios

## Troubleshooting

### Notifications not appearing

1. Check that `NotificationToaster` is in the root layout
2. Verify import paths are correct
3. Check browser console for errors

### Notifications not dismissing

1. Check duration is set correctly
2. Verify close button is rendered
3. Check for JavaScript errors

### Test IDs not found

1. Ensure you're using the custom `NotificationToaster` component
2. Check that toast is actually rendered (visible)
3. Wait for animation to complete in tests

## API Reference

See `components/SuccessNotification.tsx` for complete TypeScript definitions and JSDoc documentation.

## Examples

A complete example component is available at:
- `components/examples/NotificationExample.tsx`

To view it, import and render in any page:

```typescript
import { NotificationExample } from '@/components/examples/NotificationExample';

export default function TestPage() {
  return <NotificationExample />;
}
```

## Support

For issues or questions:
1. Check this documentation
2. Review the example component
3. Check test files for usage patterns
4. Open an issue in the project repository
