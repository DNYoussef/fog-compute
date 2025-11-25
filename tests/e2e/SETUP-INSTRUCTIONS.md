# Wave 6 E2E Tests Setup Instructions

## Quick Start

### 1. Install Dependencies

```bash
# Install axe-playwright for accessibility testing
npm install --save-dev axe-playwright

# Verify Playwright is installed
npm list @playwright/test

# Install Playwright browsers if needed
npx playwright install
```

### 2. Verify Backend is Running

```bash
# Start backend (from project root)
cd backend
python -m uvicorn server.main:app --port 8000

# Verify backend health
curl http://localhost:8000/health
```

### 3. Verify Frontend is Running

```bash
# Start frontend (from project root)
cd apps/control-panel
npm run dev

# Verify frontend
# Open http://localhost:3000 in browser
```

### 4. Run Tests

```bash
# From project root
npx playwright test test_login_flow.spec.ts
npx playwright test test_registration_flow.spec.ts
npx playwright test test_protected_routes.spec.ts

# Or run all E2E tests
npm run test:e2e
```

## Current Implementation Status

### Backend: Fully Implemented
- Registration endpoint: `POST /api/auth/register`
- Login endpoint: `POST /api/auth/login`
- User info endpoint: `GET /api/auth/me`
- Logout endpoint: `POST /api/auth/logout`
- JWT authentication
- Password hashing (bcrypt)
- Input validation

### Frontend: Partially Implemented
- Control panel exists at `/control-panel`
- **Login/Registration UI pages NOT yet implemented**
- Tests are designed to:
  1. Document expected behavior
  2. Test API directly when UI missing
  3. Pass/skip gracefully until UI implemented

## Test Execution Modes

### Mode 1: API Testing (Current)
Tests will primarily test authentication APIs directly using Playwright's `page.request` API:
```typescript
const response = await page.request.post('http://localhost:8000/api/auth/login', {
  data: { username, password }
});
```

### Mode 2: UI Testing (Future)
When login/registration pages are implemented at `/login` and `/register`, tests will:
1. Navigate to UI pages
2. Fill forms using Page Object Models
3. Verify UI behavior
4. Test full user flows

## Expected Test Results

### Current Behavior
- **API Tests**: Should PASS (backend fully implemented)
- **UI Tests**: May SKIP or FAIL GRACEFULLY (UI not implemented)
- **Protected Route Tests**: May vary (depends on frontend route guards)

### After UI Implementation
All tests should pass once:
1. Login page created at `/login`
2. Registration page created at `/register`
3. Route protection implemented (redirect to /login)
4. Form elements use data-testid attributes

## Implementing the UI

### Required Pages

#### 1. Login Page (`/login`)
Required elements with data-testid:
```tsx
<form data-testid="login-form">
  <input data-testid="username-input" name="username" type="text" />
  <input data-testid="password-input" name="password" type="password" />
  <input data-testid="remember-me" type="checkbox" name="remember" />
  <button data-testid="login-button" type="submit">Login</button>
</form>
<div data-testid="error-message" role="alert">
  {/* Error messages */}
</div>
```

#### 2. Registration Page (`/register`)
Required elements with data-testid:
```tsx
<form data-testid="register-form">
  <input data-testid="username-input" name="username" type="text" />
  <input data-testid="email-input" name="email" type="email" />
  <input data-testid="password-input" name="password" type="password" />
  <button data-testid="register-button" type="submit">Register</button>
</form>
<div data-testid="password-strength">
  {/* Password strength indicator */}
</div>
<div data-testid="error-message" role="alert">
  {/* Error messages */}
</div>
```

#### 3. Route Protection
Protected routes should redirect to `/login` when unauthenticated:
```tsx
// middleware.ts or layout.tsx
if (!isAuthenticated && isProtectedRoute) {
  redirect('/login?return=' + currentPath);
}
```

## Troubleshooting

### Problem: Tests timeout waiting for UI elements
**Solution**: These tests expect UI pages. Either:
1. Implement the UI pages (recommended)
2. Skip UI-specific tests until implementation

### Problem: Accessibility tests fail
**Solution**: Install axe-playwright:
```bash
npm install --save-dev axe-playwright
```

### Problem: Backend not responding
**Solution**: Verify backend is running:
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

### Problem: Database connection errors
**Solution**: Verify PostgreSQL is running:
```bash
# Check database URL in backend/.env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fog_compute_test
```

## Next Steps

1. **Install axe-playwright**: `npm install --save-dev axe-playwright`
2. **Run API tests**: Verify backend authentication works
3. **Implement UI pages**: Create `/login` and `/register` pages
4. **Add route protection**: Redirect to login for protected routes
5. **Run full test suite**: All tests should pass

## Integration with Existing Tests

Wave 6 tests complement existing authentication tests:
- **Existing**: `tests/e2e/authentication.spec.ts` (API-focused)
- **Wave 6**: UI flows, accessibility, comprehensive scenarios

Both test suites can coexist and provide different coverage areas.

## Questions?

Refer to:
- `tests/e2e/README-WAVE6-E2E-TESTS.md` for detailed documentation
- Existing `tests/e2e/authentication.spec.ts` for API test examples
- Playwright docs: https://playwright.dev
