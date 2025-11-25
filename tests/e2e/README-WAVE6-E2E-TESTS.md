# Wave 6 E2E Tests - Authentication UI Flows

## Overview

Wave 6 implements comprehensive End-to-End (E2E) tests for authentication UI flows using Playwright. These tests cover login, registration, and protected route scenarios with a focus on user experience, security, and accessibility.

## Test Structure

```
tests/e2e/
|-- fixtures/
|   |-- auth-fixtures.ts           # Authentication helpers and fixtures
|-- page-objects/
|   |-- LoginPage.ts                # Login page object model
|   |-- RegisterPage.ts             # Registration page object model
|-- test_login_flow.spec.ts         # TEST-05: Login UI tests (14 scenarios)
|-- test_registration_flow.spec.ts  # TEST-06: Registration UI tests (18 scenarios)
|-- test_protected_routes.spec.ts   # TEST-07: Route protection tests (15 scenarios)
```

## Test Groups

### TEST-05: Login UI E2E Tests (14 scenarios)
**File**: `test_login_flow.spec.ts`
**Time**: ~4 hours

**Scenarios**:
- L01: Display login form correctly
- L02: Successfully login with valid credentials
- L03: Fail login with wrong password
- L04: Show validation errors for empty fields
- L05: Redirect after successful login
- L06: Handle remember me functionality
- L07: Handle non-existent user gracefully
- L08: Prevent login with disabled account
- L09: Meet WCAG 2.1 Level AA standards (accessibility)
- L10: Be keyboard navigable (accessibility)
- L11: Not expose password in DOM (security)
- L12: Clear form after failed login attempt (security)
- L13: Load login page within 3 seconds (performance)
- L14: Handle rapid login attempts gracefully (performance)

### TEST-06: Registration UI E2E Tests (18 scenarios)
**File**: `test_registration_flow.spec.ts`
**Time**: ~4 hours

**Scenarios**:
- R01: Display registration form correctly
- R02: Successfully register a new user
- R03: Prevent duplicate email registration
- R04: Prevent duplicate username registration
- R05: Validate email format
- R06: Enforce password strength requirements
- R07: Show password strength indicator
- R08: Validate username format
- R09: Validate required fields
- R10: Match password confirmation
- R11: Handle email verification if implemented
- R12: Meet WCAG 2.1 Level AA standards (accessibility)
- R13: Be keyboard navigable (accessibility)
- R14: Have proper ARIA labels (accessibility)
- R15: Not expose sensitive data in network logs (security)
- R16: Use HTTPS in production (security)
- R17: Load registration page within 3 seconds (performance)
- R18: Handle registration within 5 seconds (performance)

### TEST-07: Protected Routes E2E Tests (15 scenarios)
**File**: `test_protected_routes.spec.ts`
**Time**: ~4 hours

**Scenarios**:
- P01: Block unauthenticated access to protected routes
- P02: Allow authenticated access to protected routes
- P03: Redirect to login page with return URL
- P04: Preserve intended route after login
- P05: Enforce admin-only routes (RBAC)
- P06: Allow admin access to admin routes (RBAC)
- P07: Hide admin UI elements from regular users (RBAC)
- P08: Handle session expiration
- P09: Clear session on logout
- P10: Maintain session across page reloads
- P11: Handle concurrent sessions
- P12: Reject tampered tokens (security)
- P13: Handle missing authorization header (security)
- P14: Validate token on every protected request (security)
- P15: Protected routes should meet accessibility standards

## Key Features

### 1. Page Object Model (POM)
- **LoginPage.ts**: Encapsulates login page interactions
- **RegisterPage.ts**: Encapsulates registration page interactions
- Benefits: Maintainability, reusability, cleaner test code

### 2. Reusable Fixtures
- **auth-fixtures.ts**: Provides authentication helpers
  - `generateTestUser()`: Creates unique test user data
  - `AuthHelper`: Authentication utilities (register, login, token management)
  - `authenticatedPage`: Pre-authenticated page fixture
  - `testUser`: Unique test user fixture

### 3. Accessibility Testing
- Integrated **axe-core** for WCAG 2.1 Level AA compliance
- Keyboard navigation tests
- ARIA label verification
- Screen reader compatibility

### 4. Security Testing
- Token validation and tampering detection
- Password exposure prevention
- HTTPS enforcement (production)
- Session management security

### 5. Performance Testing
- Page load time benchmarks
- Form submission performance
- Rapid interaction handling

## Running Tests

### Prerequisites
```bash
# Install dependencies
npm install

# Install Playwright browsers
npx playwright install
```

### Run All Wave 6 Tests
```bash
# Run all E2E tests
npm run test:e2e

# Run specific test group
npx playwright test test_login_flow.spec.ts
npx playwright test test_registration_flow.spec.ts
npx playwright test test_protected_routes.spec.ts

# Run with UI mode (interactive)
npx playwright test --ui

# Run in headed mode (visible browser)
npx playwright test --headed
```

### Run Tests by Tag/Scenario
```bash
# Run only accessibility tests
npx playwright test --grep "Accessibility"

# Run only security tests
npx playwright test --grep "Security"

# Run only performance tests
npx playwright test --grep "Performance"

# Skip slow tests
npx playwright test --grep-invert "slow"
```

### Debug Tests
```bash
# Debug mode with Playwright Inspector
npx playwright test --debug

# Debug specific test
npx playwright test test_login_flow.spec.ts:20 --debug

# Generate trace for debugging
npx playwright test --trace on
```

### CI/CD Execution
```bash
# Headless mode with multiple workers
npx playwright test --workers=4

# Generate reports
npx playwright test --reporter=html,json,junit

# Run on specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

## Test Data Management

### Dynamic Test Users
Tests generate unique users per run to avoid conflicts:
```typescript
const testUser = {
  username: `e2euser${Date.now()}${Math.random()}`,
  email: `e2e${Date.now()}@example.com`,
  password: 'TestPassword123!'
};
```

### Test Isolation
- Each test creates its own user data
- Authentication state is cleared before each test
- No shared state between tests
- Parallel execution safe

## Expected Behavior

### Current Implementation Status
The fog-compute project currently has:
- **Backend**: Full authentication API (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`)
- **Frontend**: Next.js control panel but **NO dedicated login/registration UI pages yet**

### Test Behavior
These tests are designed to:
1. **Document expected behavior** for when UI is implemented
2. **Test API endpoints** directly when UI doesn't exist
3. **Gracefully handle missing UI elements** (tests will skip or fail gracefully)
4. **Provide specifications** for frontend developers

### Skipped Tests
Tests that require UI components not yet implemented will:
- Use `.skip()` for scenarios requiring UI
- Test API directly as fallback
- Pass when API works correctly
- Provide clear failure messages when UI is needed

## Browser Compatibility

Tests run on multiple browsers:
- **Chromium** (Chrome, Edge)
- **Firefox**
- **WebKit** (Safari)
- **Mobile** (Chrome Mobile, Safari Mobile)

## Accessibility Standards

Tests verify WCAG 2.1 Level AA compliance:
- Color contrast
- Keyboard navigation
- Screen reader compatibility
- Focus management
- ARIA labels and roles
- Form validation announcements

## Security Best Practices Tested

1. **Token Management**:
   - JWT format validation
   - Token expiration handling
   - Secure storage (localStorage)

2. **Password Security**:
   - Type="password" enforcement
   - No password exposure in DOM/logs
   - Strong password requirements

3. **Session Management**:
   - Session persistence
   - Logout functionality
   - Concurrent session handling

4. **Route Protection**:
   - Unauthenticated blocking
   - Token validation on every request
   - Tampered token rejection

## Performance Benchmarks

- **Page Load**: < 3 seconds
- **Form Submission**: < 5 seconds
- **API Response**: < 2 seconds
- **Navigation**: < 1 second

## Troubleshooting

### Tests Fail: "Element not found"
**Cause**: UI components not yet implemented
**Solution**: Tests are documenting expected behavior. Implement UI components or skip tests.

### Tests Timeout
**Cause**: Backend not running or database not initialized
**Solution**: Ensure backend is running on port 8000 and database is accessible.

### Authentication Failures
**Cause**: Token storage or API endpoint issues
**Solution**: Check browser console and network tab for errors.

### Accessibility Failures
**Cause**: Missing ARIA labels or keyboard navigation
**Solution**: Review axe-core report and implement recommended fixes.

## Maintenance

### Adding New Tests
1. Create test in appropriate spec file
2. Use Page Object Model for UI interactions
3. Use auth fixtures for authentication
4. Include accessibility and security checks
5. Add performance benchmarks

### Updating Page Objects
When UI changes:
1. Update locators in `LoginPage.ts` or `RegisterPage.ts`
2. Add new methods for new interactions
3. Update documentation

### Updating Fixtures
When auth flow changes:
1. Update `AuthHelper` in `auth-fixtures.ts`
2. Update fixture definitions
3. Test fixture changes in isolation

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: E2E Tests - Wave 6

on: [push, pull_request]

jobs:
  e2e-auth-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npm run test:e2e
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

## Future Enhancements

1. **Visual Regression Testing**: Screenshot comparison across UI changes
2. **API Mocking**: Mock backend for faster tests
3. **Test Data Factory**: More sophisticated test data generation
4. **Multi-Factor Authentication**: Tests for 2FA flows
5. **Social Login**: Tests for OAuth providers
6. **Password Reset**: Tests for password recovery flow

## Documentation References

- [Playwright Documentation](https://playwright.dev)
- [Axe-core Accessibility Testing](https://github.com/dequelabs/axe-core)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

## Contributors

This test suite was generated as part of Wave 6 E2E implementation for the fog-compute project.

## License

Follows fog-compute project license.
