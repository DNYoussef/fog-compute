# Notification System - Cheat Sheet

## Quick Reference Card for Developers

---

## Import

```typescript
import { showSuccess, showError, showWarning, showInfo } from '@/components/SuccessNotification';
```

---

## Basic Usage

### Success
```typescript
showSuccess('Operation completed');
```

### Error
```typescript
showError('Operation failed');
```

### Warning
```typescript
showWarning('Potential issue detected');
```

### Info
```typescript
showInfo('FYI: Something happened');
```

---

## Common Patterns

### Form Submit
```typescript
try {
  await saveForm(data);
  showSuccess('Form saved');
} catch (error) {
  showError(`Save failed: ${error.message}`);
}
```

### API Call
```typescript
import { showPromise } from '@/components/SuccessNotification';

showPromise(
  api.update(id, data),
  {
    loading: 'Updating...',
    success: 'Updated!',
    error: (err) => `Failed: ${err.message}`
  }
);
```

### Loading
```typescript
import { showLoading, dismissNotification } from '@/components/SuccessNotification';

const id = showLoading('Processing...');
await doWork();
dismissNotification(id);
showSuccess('Done!');
```

---

## Options

```typescript
showSuccess('Message', {
  duration: 10000,        // 10 seconds
  position: 'top-right',  // top-left, top-center, etc.
  icon: '🚀',            // custom icon
  id: 'unique-id'         // for deduplication
});
```

---

## Test IDs

- `success-notification` - Success toasts
- `error-notification` - Error toasts
- `loading-notification` - Loading toasts
- `notification-message` - Message content
- `notification-close` - Close button

---

## E2E Test Example

```typescript
await page.click('[data-testid="save-button"]');
await page.waitForSelector('[data-testid="success-notification"]');
expect(await page.textContent('[data-testid="notification-message"]'))
  .toContain('Settings saved');
```

---

## Best Practices

✅ **Do**:
- Use appropriate types (success/error/warning/info)
- Keep messages concise and actionable
- Use promise notifications for async operations
- Include error context in error messages

❌ **Don't**:
- Spam users with too many notifications
- Use generic messages like "Error" or "Success"
- Forget to handle errors
- Use notifications for debugging

---

## Examples

### Resource Limits
```typescript
showSuccess('Resource limits updated: CPU 8 cores, Memory 16GB');
```

### Node Deployment
```typescript
showPromise(
  deployNode(nodeId),
  {
    loading: 'Deploying node...',
    success: 'Node deployed successfully',
    error: (err) => `Deployment failed: ${err.message}`
  }
);
```

### Configuration
```typescript
showSuccess('Configuration saved - changes will apply in 30 seconds');
```

### API Key
```typescript
showInfo('API key regenerated - please update your clients');
```

---

## Full Documentation

- **Quick Start**: `docs/NOTIFICATION_QUICK_START.md`
- **Integration Guide**: `docs/NOTIFICATION_INTEGRATION_GUIDE.md`
- **Usage Examples**: `docs/NOTIFICATION_USAGE_EXAMPLES.md`
- **Implementation**: `docs/NOTIFICATION_IMPLEMENTATION_SUMMARY.md`

---

## Support

Questions? Check the docs or contact the dev team.
