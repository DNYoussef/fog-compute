# Jest Setup Library Component

LEGO-compatible Jest + React Testing Library setup for React 18/19 projects with TypeScript.

**Deployed from**: `~/.claude/library/components/testing/jest-setup/`
**Target**: fog-compute project
**Date**: 2026-01-15

## Installation

### 1. Install Dependencies

The following dependencies should already be in package.json:

```bash
npm install -D jest @types/jest ts-jest @testing-library/react @testing-library/jest-dom @testing-library/user-event @tanstack/react-query react-router-dom
```

### 2. Configure Jest

Update `jest.config.js` to include the module path mapper:

```javascript
moduleNameMapper: {
  // ... existing mappers
  '^jest-setup/(.*)$': '<rootDir>/tools/testing/jest-setup/$1',
  '^jest-setup$': '<rootDir>/tools/testing/jest-setup/index',
},
```

## Quick Start

```typescript
import { render, screen } from 'jest-setup/test-utils';
import userEvent from '@testing-library/user-event';
import { Button } from '../Button';

test('button click', async () => {
  const onClick = jest.fn();
  render(<Button onClick={onClick}>Click me</Button>);
  await userEvent.click(screen.getByRole('button'));
  expect(onClick).toHaveBeenCalled();
});
```

## Custom Matchers

```typescript
expect('{"valid": true}').toBeValidJSON();
expect(mockFn).toHaveBeenCalledWithMatch({ id: expect.any(String) });
expect(5).toBeWithinRange(1, 10);
expect(response).toMatchAPIResponse({ status: 200 });
expect([1, 2, 3]).toBeSorted();
expect(obj).toHaveKeys(['id', 'name']);
```

## Built-in Mocks

| API | Mock Behavior |
|-----|---------------|
| ResizeObserver | Triggers callback immediately |
| IntersectionObserver | Reports element as visible |
| localStorage | In-memory storage |
| sessionStorage | In-memory storage |
| matchMedia | Returns matches: false |
| scrollTo | No-op |
| fetch | Returns empty successful response |

## File Structure

```
tools/testing/jest-setup/
  index.ts       # Package exports
  setup.ts       # Global setup and mocks
  test-utils.tsx # Custom render with providers
  matchers.ts    # Custom Jest matchers
  README.md      # This documentation
```

## Mock Utilities

### mockAPIResponse

```typescript
import { mockAPIResponse } from 'jest-setup/setup';

global.fetch = jest.fn().mockResolvedValue(
  mockAPIResponse({ users: [{ id: '1', name: 'Test' }] })
);
```

### createMockFetch

```typescript
import { createMockFetch } from 'jest-setup/setup';

global.fetch = createMockFetch({
  '/api/users': { data: [{ id: '1' }] },
  '/api/projects': { data: [] },
});
```

## Version

1.0.0 - Initial deployment to fog-compute (2026-01-15)
