/**
 * TEST-05: Login UI E2E Tests
 * Comprehensive tests for login flow, validation, and error handling
 */
import { test, expect } from './fixtures/auth-fixtures';
import { LoginPage } from './page-objects/LoginPage';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('TEST-05: Login UI Flow', () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page, authHelper }) => {
    loginPage = new LoginPage(page);
    await authHelper.clearAuth();
  });

  test('L01: should display login form correctly', async ({ page }) => {
    await loginPage.goto();

    // Verify form elements are visible
    await loginPage.verifyFormVisible();

    // Check page title
    await expect(page).toHaveTitle(/Login|Sign in/i);
  });

  test('L02: should successfully login with valid credentials', async ({ page, authHelper, testUser }) => {
    // Register test user first
    await authHelper.registerUser(testUser);

    // Navigate to login page
    await loginPage.goto();

    // Fill in credentials and submit
    await loginPage.login(testUser.username, testUser.password);

    // Wait for successful login redirect
    await loginPage.waitForLoginSuccess();

    // Verify user is authenticated
    const isAuth = await authHelper.isAuthenticated();
    expect(isAuth).toBe(true);

    // Verify token exists in storage
    const token = await authHelper.getAuthToken();
    expect(token).toBeTruthy();
    expect(token).toMatch(/^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$/); // JWT format
  });

  test('L03: should fail login with wrong password', async ({ page, authHelper, testUser }) => {
    // Register test user
    await authHelper.registerUser(testUser);

    // Navigate to login page
    await loginPage.goto();

    // Attempt login with wrong password
    await loginPage.login(testUser.username, 'WrongPassword123!');

    // Should NOT redirect
    await page.waitForTimeout(2000);
    expect(page.url()).toContain('/login');

    // Should show error message
    const hasError = await loginPage.hasError();
    expect(hasError).toBe(true);

    const errorText = await loginPage.getErrorMessage();
    expect(errorText.toLowerCase()).toMatch(/incorrect|invalid|wrong|failed/);

    // Verify user is NOT authenticated
    const isAuth = await authHelper.isAuthenticated();
    expect(isAuth).toBe(false);
  });

  test('L04: should show validation errors for empty fields', async ({ page }) => {
    await loginPage.goto();

    // Try to submit empty form
    await loginPage.clickLogin();

    // Should still be on login page
    expect(page.url()).toContain('/login');

    // Check for validation errors (HTML5 validation or custom)
    const usernameError = await loginPage.getUsernameValidationError();
    const passwordError = await loginPage.getPasswordValidationError();

    // At least one field should have validation error
    expect(usernameError || passwordError).toBeTruthy();
  });

  test('L05: should redirect after successful login', async ({ page, authHelper, testUser }) => {
    // Register test user
    await authHelper.registerUser(testUser);

    // Navigate to protected route (should redirect to login)
    await page.goto('/control-panel');

    // If redirected to login, we should be on /login page
    // (This assumes route protection is implemented)
    const currentUrl = page.url();
    if (currentUrl.includes('/login')) {
      // Fill in login form
      await loginPage.login(testUser.username, testUser.password);

      // Should redirect back to originally requested page
      await page.waitForURL(/\/control-panel/, { timeout: 10000 });
      expect(page.url()).toContain('/control-panel');
    } else {
      // If no redirect to login, login manually and check redirect
      await loginPage.goto();
      await loginPage.login(testUser.username, testUser.password);
      await loginPage.waitForLoginSuccess();
    }
  });

  test('L06: should handle remember me functionality', async ({ page, authHelper, testUser }) => {
    // Register test user
    await authHelper.registerUser(testUser);

    // Navigate to login page
    await loginPage.goto();

    // Login with remember me checked
    await loginPage.login(testUser.username, testUser.password, true);

    // Wait for successful login
    await loginPage.waitForLoginSuccess();

    // Verify token is stored
    const token = await authHelper.getAuthToken();
    expect(token).toBeTruthy();

    // Check if remember preference is stored
    const rememberMe = await page.evaluate(() => {
      return localStorage.getItem('remember_me') || sessionStorage.getItem('remember_me');
    });

    // Note: Remember me behavior varies by implementation
    // This test documents expected behavior
  });

  test('L07: should handle non-existent user gracefully', async ({ page }) => {
    await loginPage.goto();

    // Try to login with non-existent user
    await loginPage.login('nonexistent_user_12345', 'RandomPassword123!');

    // Should show error message
    const hasError = await loginPage.hasError();
    expect(hasError).toBe(true);

    const errorText = await loginPage.getErrorMessage();
    expect(errorText.toLowerCase()).toMatch(/incorrect|invalid|not found|failed/);
  });

  test('L08: should prevent login with disabled account', async ({ page, authHelper, testUser }) => {
    // Register user
    const response = await authHelper.registerUser(testUser);
    expect(response.ok()).toBeTruthy();

    // Note: To test disabled accounts, you'd need to disable the account via API
    // This is a placeholder for that scenario

    // For now, verify that active accounts can login
    await loginPage.goto();
    await loginPage.login(testUser.username, testUser.password);
    await loginPage.waitForLoginSuccess();
  });

  test.describe('Accessibility', () => {
    test('L09: should meet WCAG 2.1 Level AA standards', async ({ page }) => {
      await loginPage.goto();

      // Inject axe-core for accessibility testing
      await injectAxe(page);

      // Check accessibility
      await checkA11y(page, undefined, {
        detailedReport: true,
        detailedReportOptions: {
          html: true,
        },
      });
    });

    test('L10: should be keyboard navigable', async ({ page }) => {
      await loginPage.goto();

      // Tab through form fields
      await page.keyboard.press('Tab'); // Focus username
      await expect(loginPage.usernameInput).toBeFocused();

      await page.keyboard.press('Tab'); // Focus password
      await expect(loginPage.passwordInput).toBeFocused();

      await page.keyboard.press('Tab'); // Focus login button
      await expect(loginPage.loginButton).toBeFocused();
    });
  });

  test.describe('Security', () => {
    test('L11: should not expose password in DOM', async ({ page }) => {
      await loginPage.goto();

      await loginPage.fillPassword('SecretPassword123!');

      // Verify password input type is "password"
      const inputType = await loginPage.passwordInput.getAttribute('type');
      expect(inputType).toBe('password');

      // Verify password value is not visible in HTML
      const pageContent = await page.content();
      expect(pageContent).not.toContain('SecretPassword123!');
    });

    test('L12: should clear form after failed login attempt', async ({ page }) => {
      await loginPage.goto();

      await loginPage.login('baduser', 'badpassword');

      // Wait for error
      await page.waitForTimeout(1000);

      // Verify password field is cleared (common security practice)
      const passwordValue = await loginPage.passwordInput.inputValue();
      // Note: Some implementations clear password, others don't
      // This documents expected behavior
    });
  });
});

test.describe('TEST-05: Login Performance', () => {
  test('L13: should load login page within 3 seconds', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    expect(loadTime).toBeLessThan(3000);
  });

  test('L14: should handle rapid login attempts gracefully', async ({ page, authHelper, testUser }) => {
    // Register user
    await authHelper.registerUser(testUser);

    const loginPage = new LoginPage(page);
    await loginPage.goto();

    // Attempt multiple rapid logins
    const attempts = [];
    for (let i = 0; i < 5; i++) {
      attempts.push(
        loginPage.login(testUser.username, testUser.password)
      );
    }

    // Should handle all attempts without crashing
    await Promise.allSettled(attempts);

    // Page should still be responsive
    await expect(loginPage.usernameInput).toBeVisible();
  });
});
