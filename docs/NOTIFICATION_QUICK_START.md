# Notification System - Quick Start

## Installation

The notification system is already installed and configured. No additional setup needed!

## Import

```typescript
import { showSuccess, showError, showWarning, showInfo } from '@/components/SuccessNotification';
```

## Basic Usage

### Success
```typescript
showSuccess('Resource limits updated successfully');
```

### Error
```typescript
showError('Failed to deploy node: Connection timeout');
```

### Warning
```typescript
showWarning('Node performance degraded');
```

### Info
```typescript
showInfo('Node discovery in progress...');
```

## Common Patterns

### Form Submission
```typescript
try {
  await saveForm(data);
  showSuccess('Form saved successfully');
} catch (error) {
  showError(`Save failed: ${error.message}`);
}
```

### API Calls
```typescript
import { showPromise } from '@/components/SuccessNotification';

showPromise(
  api.updateResource(id, data),
  {
    loading: 'Updating resource...',
    success: 'Resource updated successfully',
    error: (err) => `Update failed: ${err.message}`
  }
);
```

### Loading States
```typescript
import { showLoading, dismissNotification, showSuccess } from '@/components/SuccessNotification';

const id = showLoading('Processing...');
try {
  await doWork();
  dismissNotification(id);
  showSuccess('Completed!');
} catch (error) {
  dismissNotification(id);
  showError('Failed!');
}
```

## Test IDs

All notifications include test IDs for E2E testing:

- `data-testid="success-notification"` - Success toasts
- `data-testid="error-notification"` - Error toasts
- `data-testid="loading-notification"` - Loading toasts
- `data-testid="notification-message"` - Message content
- `data-testid="notification-close"` - Close button

## Example Component

See full examples at: `components/examples/NotificationExample.tsx`

## More Details

For complete API reference and advanced usage, see: `docs/NOTIFICATION_INTEGRATION_GUIDE.md`
