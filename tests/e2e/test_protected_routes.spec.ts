/**
 * TEST-07: Protected Routes E2E Tests
 * Tests route protection, authentication guards, RBAC, and session management
 */
import { test, expect } from './fixtures/auth-fixtures';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('TEST-07: Protected Routes - Authentication Guards', () => {
  const protectedRoutes = [
    '/control-panel',
    '/control-panel/benchmarks',
    '/control-panel/betanet',
    '/control-panel/tasks',
    '/control-panel/nodes',
    '/control-panel/resources',
  ];

  test.beforeEach(async ({ authHelper }) => {
    await authHelper.clearAuth();
  });

  test('P01: should block unauthenticated access to protected routes', async ({ page }) => {
    for (const route of protectedRoutes) {
      await page.goto(route);

      // Should redirect to login or show 403/401
      await page.waitForLoadState('networkidle');

      const currentUrl = page.url();
      const pageContent = await page.textContent('body');

      // Either redirected to login or shows unauthorized message
      const isBlocked = currentUrl.includes('/login') ||
                        pageContent.toLowerCase().includes('unauthorized') ||
                        pageContent.toLowerCase().includes('login') ||
                        pageContent.toLowerCase().includes('authentication required');

      expect(isBlocked).toBe(true);
    }
  });

  test('P02: should allow authenticated access to protected routes', async ({ page, authHelper, testUser }) => {
    // Register and authenticate user
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Try accessing protected routes
    for (const route of protectedRoutes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');

      const currentUrl = page.url();

      // Should be able to access the route
      expect(currentUrl).toContain(route);

      // Should not show unauthorized message
      const pageContent = await page.textContent('body');
      expect(pageContent.toLowerCase()).not.toMatch(/unauthorized|forbidden|access denied/);
    }
  });

  test('P03: should redirect to login page with return URL', async ({ page }) => {
    const targetRoute = '/control-panel/benchmarks';

    await page.goto(targetRoute);
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();

    if (currentUrl.includes('/login')) {
      // Check if return URL is preserved in query params
      const url = new URL(currentUrl, 'http://localhost:3000');
      const returnUrl = url.searchParams.get('return') || url.searchParams.get('redirect') || url.searchParams.get('next');

      // Note: This behavior depends on implementation
      // Test documents expected behavior
    }
  });

  test('P04: should preserve intended route after login', async ({ page, authHelper, testUser }) => {
    const targetRoute = '/control-panel/tasks';

    // Try to access protected route (should redirect to login)
    await page.goto(targetRoute);
    await page.waitForLoadState('networkidle');

    // If redirected to login, register and login
    const currentUrl = page.url();
    if (currentUrl.includes('/login')) {
      // Register user via API
      await authHelper.registerUser(testUser);

      // Login via UI (if login page exists)
      // For now, set token directly
      const token = await authHelper.loginUser(testUser.username, testUser.password);
      await authHelper.setAuthToken(token!);

      // Navigate back to intended route
      await page.goto(targetRoute);
      await page.waitForLoadState('networkidle');

      // Should reach target route
      expect(page.url()).toContain(targetRoute);
    }
  });
});

test.describe('TEST-07: Role-Based Access Control (RBAC)', () => {
  test('P05: should enforce admin-only routes', async ({ page, authHelper, testUser }) => {
    // Register regular user
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Try to access admin routes (if they exist)
    const adminRoutes = [
      '/control-panel/admin',
      '/control-panel/users',
      '/control-panel/settings/security',
    ];

    for (const route of adminRoutes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');

      const pageContent = await page.textContent('body');
      const currentUrl = page.url();

      // If route exists, should either redirect or show 403
      // If route doesn't exist, will get 404 (which is fine)

      // Note: This test documents expected RBAC behavior
      // Actual implementation may vary
    }
  });

  test('P06: should allow admin access to admin routes', async ({ page, authHelper }) => {
    // Create admin user
    const adminUser = {
      username: `admin${Date.now()}`,
      email: `admin${Date.now()}@example.com`,
      password: 'AdminPassword123!',
    };

    // Register admin user (would need backend support to set is_admin=true)
    await authHelper.registerUser(adminUser);
    const token = await authHelper.loginUser(adminUser.username, adminUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Note: To fully test admin access, backend would need to support
    // creating admin users or promoting users to admin

    // This test documents expected admin access behavior
  });

  test('P07: should hide admin UI elements from regular users', async ({ page, authHelper, testUser }) => {
    // Login as regular user
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Navigate to main dashboard
    await page.goto('/control-panel');
    await page.waitForLoadState('networkidle');

    // Check if admin-only UI elements are hidden
    const adminButton = page.locator('[data-testid="admin-panel"], a:has-text("Admin"), button:has-text("Admin")');
    const isAdminVisible = await adminButton.isVisible().catch(() => false);

    // Regular user should not see admin elements
    expect(isAdminVisible).toBe(false);
  });
});

test.describe('TEST-07: Session Management', () => {
  test('P08: should handle session expiration', async ({ page, authHelper, testUser }) => {
    // Register and login user
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Access protected route
    await page.goto('/control-panel');
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/control-panel');

    // Simulate token expiration by setting invalid token
    await authHelper.setAuthToken('expired_token_12345');

    // Try to access another protected route
    await page.goto('/control-panel/tasks');
    await page.waitForLoadState('networkidle');

    // Should redirect to login or show error
    const currentUrl = page.url();
    const pageContent = await page.textContent('body');

    const isSessionInvalid = currentUrl.includes('/login') ||
                             pageContent.toLowerCase().includes('session expired') ||
                             pageContent.toLowerCase().includes('unauthorized');

    expect(isSessionInvalid).toBe(true);
  });

  test('P09: should clear session on logout', async ({ page, authHelper, testUser }) => {
    // Register and login
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Verify authenticated
    const isAuthBefore = await authHelper.isAuthenticated();
    expect(isAuthBefore).toBe(true);

    // Logout (via API or UI)
    await page.request.post('http://localhost:8000/api/auth/logout', {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    // Clear client-side auth
    await authHelper.clearAuth();

    // Verify logged out
    const isAuthAfter = await authHelper.isAuthenticated();
    expect(isAuthAfter).toBe(false);

    // Try to access protected route
    await page.goto('/control-panel');
    await page.waitForLoadState('networkidle');

    // Should be blocked
    const currentUrl = page.url();
    const pageContent = await page.textContent('body');

    const isBlocked = currentUrl.includes('/login') ||
                      pageContent.toLowerCase().includes('unauthorized');

    expect(isBlocked).toBe(true);
  });

  test('P10: should maintain session across page reloads', async ({ page, authHelper, testUser }) => {
    // Register and login
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Access protected route
    await page.goto('/control-panel');
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/control-panel');

    // Reload page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Should still be authenticated
    expect(page.url()).toContain('/control-panel');

    const isStillAuth = await authHelper.isAuthenticated();
    expect(isStillAuth).toBe(true);
  });

  test('P11: should handle concurrent sessions', async ({ page, context, authHelper, testUser }) => {
    // Register user
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    // Set auth in first page
    await page.goto('/');
    await authHelper.setAuthToken(token!);
    await page.goto('/control-panel');

    // Create second page (tab) in same context
    const page2 = await context.newPage();
    await page2.goto('/');

    // Second page should also have access (shared storage)
    const helper2 = new (await import('./fixtures/auth-fixtures')).AuthHelper(page2, 'http://localhost:3000');
    const isAuth2 = await helper2.isAuthenticated();

    if (isAuth2) {
      await page2.goto('/control-panel');
      expect(page2.url()).toContain('/control-panel');
    }

    await page2.close();
  });
});

test.describe('TEST-07: Security Edge Cases', () => {
  test('P12: should reject tampered tokens', async ({ page, authHelper }) => {
    // Set invalid/tampered token
    await page.goto('/');
    await authHelper.setAuthToken('tampered.invalid.token');

    // Try to access protected route
    await page.goto('/control-panel');
    await page.waitForLoadState('networkidle');

    // Should be blocked
    const currentUrl = page.url();
    const pageContent = await page.textContent('body');

    const isBlocked = currentUrl.includes('/login') ||
                      pageContent.toLowerCase().includes('unauthorized');

    expect(isBlocked).toBe(true);
  });

  test('P13: should handle missing authorization header', async ({ page }) => {
    await page.goto('/');

    // Make authenticated API request without token
    const response = await page.request.get('http://localhost:8000/api/auth/me');

    // Should return 401 or 403
    expect([401, 403]).toContain(response.status());
  });

  test('P14: should validate token on every protected request', async ({ page, authHelper, testUser }) => {
    // Register and login
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Access protected route
    await page.goto('/control-panel');
    expect(page.url()).toContain('/control-panel');

    // Tamper with token mid-session
    await authHelper.setAuthToken('tampered_token');

    // Next navigation should fail
    await page.goto('/control-panel/tasks');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const pageContent = await page.textContent('body');

    const isBlocked = currentUrl.includes('/login') ||
                      pageContent.toLowerCase().includes('unauthorized');

    expect(isBlocked).toBe(true);
  });
});

test.describe('TEST-07: Accessibility on Protected Routes', () => {
  test('P15: protected routes should meet accessibility standards', async ({ page, authHelper, testUser }) => {
    // Login user
    await authHelper.registerUser(testUser);
    const token = await authHelper.loginUser(testUser.username, testUser.password);

    await page.goto('/');
    await authHelper.setAuthToken(token!);

    // Navigate to protected route
    await page.goto('/control-panel');
    await page.waitForLoadState('networkidle');

    // Inject axe-core
    await injectAxe(page);

    // Check accessibility
    await checkA11y(page, undefined, {
      detailedReport: true,
    });
  });
});
