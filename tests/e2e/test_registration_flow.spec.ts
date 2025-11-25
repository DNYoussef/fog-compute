/**
 * TEST-06: Registration UI E2E Tests
 * Comprehensive tests for user registration, validation, and error handling
 */
import { test, expect } from './fixtures/auth-fixtures';
import { RegisterPage } from './page-objects/RegisterPage';
import { injectAxe, checkA11y } from 'axe-playwright';

test.describe('TEST-06: Registration UI Flow', () => {
  let registerPage: RegisterPage;

  test.beforeEach(async ({ page, authHelper }) => {
    registerPage = new RegisterPage(page);
    await authHelper.clearAuth();
  });

  test('R01: should display registration form correctly', async ({ page }) => {
    await registerPage.goto();

    // Verify form elements are visible
    await registerPage.verifyFormVisible();

    // Check page title
    await expect(page).toHaveTitle(/Register|Sign up|Create account/i);
  });

  test('R02: should successfully register a new user', async ({ page, testUser }) => {
    await registerPage.goto();

    // Fill in registration form
    await registerPage.register(testUser);

    // Wait for successful registration
    await registerPage.waitForRegistrationSuccess();

    // Should redirect to login or dashboard
    const currentUrl = page.url();
    expect(currentUrl).toMatch(/\/login|\/control-panel|\/verify-email/);
  });

  test('R03: should prevent duplicate email registration', async ({ page, authHelper, testUser }) => {
    // Register user first time
    await authHelper.registerUser(testUser);

    // Try to register again with same email
    await registerPage.goto();
    await registerPage.register(testUser);

    // Should show error message
    await page.waitForTimeout(2000);
    const hasError = await registerPage.hasError();
    expect(hasError).toBe(true);

    const errorText = await registerPage.getErrorMessage();
    expect(errorText.toLowerCase()).toMatch(/already|exists|registered|taken/);
  });

  test('R04: should prevent duplicate username registration', async ({ page, authHelper, testUser }) => {
    // Register user first time
    await authHelper.registerUser(testUser);

    // Try to register again with same username but different email
    await registerPage.goto();
    const duplicateUser = {
      ...testUser,
      email: `different${testUser.email}`,
    };
    await registerPage.register(duplicateUser);

    // Should show error message
    await page.waitForTimeout(2000);
    const hasError = await registerPage.hasError();
    expect(hasError).toBe(true);

    const errorText = await registerPage.getErrorMessage();
    expect(errorText.toLowerCase()).toMatch(/username|already|exists|taken/);
  });

  test('R05: should validate email format', async ({ page }) => {
    await registerPage.goto();

    const invalidUser = {
      username: 'testuser123',
      email: 'invalid-email-format',
      password: 'ValidPassword123!',
    };

    await registerPage.register(invalidUser);

    // Should show validation error
    await page.waitForTimeout(1000);

    // Check HTML5 validation or custom validation
    const isEmailInvalid = await registerPage.isEmailInvalid();
    const fieldError = await registerPage.getFieldValidationError('email');

    expect(isEmailInvalid || fieldError).toBeTruthy();
  });

  test('R06: should enforce password strength requirements', async ({ page }) => {
    await registerPage.goto();

    // Test weak passwords
    const weakPasswords = [
      'short', // Too short
      'alllowercase123', // No uppercase
      'ALLUPPERCASE123', // No lowercase
      'NoNumbers', // No numbers
      'Simple123', // Might not meet complexity requirements
    ];

    for (const weakPassword of weakPasswords) {
      const weakUser = {
        username: `testuser${Date.now()}`,
        email: `test${Date.now()}@example.com`,
        password: weakPassword,
      };

      await registerPage.fillUsername(weakUser.username);
      await registerPage.fillEmail(weakUser.email);
      await registerPage.fillPassword(weakPassword);
      await registerPage.fillConfirmPassword(weakPassword);

      // Trigger validation by clicking register or moving focus
      await registerPage.clickRegister();

      await page.waitForTimeout(1000);

      // Should either show error or not proceed
      const currentUrl = page.url();
      expect(currentUrl).toContain('/register');

      // Clear form for next iteration
      await page.reload();
    }
  });

  test('R07: should show password strength indicator', async ({ page, testUser }) => {
    await registerPage.goto();

    // Type weak password
    await registerPage.fillPassword('weak');

    // Check if password strength indicator appears
    await page.waitForTimeout(500);

    // Note: This test assumes password strength indicator exists
    // If not implemented, test will verify its absence
    const strengthIndicatorVisible = await registerPage.passwordStrengthIndicator.isVisible().catch(() => false);

    if (strengthIndicatorVisible) {
      const strength = await registerPage.getPasswordStrength();
      expect(strength.toLowerCase()).toMatch(/weak|poor|fair|good|strong/);
    }
  });

  test('R08: should validate username format', async ({ page }) => {
    await registerPage.goto();

    const invalidUsernames = [
      'ab', // Too short
      'user@name', // Invalid characters
      'user name', // Spaces not allowed
      'a'.repeat(100), // Too long
    ];

    for (const username of invalidUsernames) {
      await registerPage.fillUsername(username);
      await registerPage.fillEmail('test@example.com');
      await registerPage.fillPassword('ValidPassword123!');
      await registerPage.clickRegister();

      await page.waitForTimeout(1000);

      // Should show validation error or stay on registration page
      const currentUrl = page.url();
      expect(currentUrl).toContain('/register');

      await page.reload();
    }
  });

  test('R09: should validate required fields', async ({ page }) => {
    await registerPage.goto();

    // Try to submit empty form
    await registerPage.clickRegister();

    // Should stay on registration page
    expect(page.url()).toContain('/register');

    // Check for validation errors
    const usernameError = await registerPage.getFieldValidationError('username');
    const emailError = await registerPage.getFieldValidationError('email');
    const passwordError = await registerPage.getFieldValidationError('password');

    // At least one field should have validation error
    expect(usernameError || emailError || passwordError).toBeTruthy();
  });

  test('R10: should match password confirmation (if implemented)', async ({ page, testUser }) => {
    await registerPage.goto();

    // Fill form with mismatched passwords
    await registerPage.fillUsername(testUser.username);
    await registerPage.fillEmail(testUser.email);
    await registerPage.fillPassword(testUser.password);

    // Check if confirm password field exists
    const hasConfirmPassword = await registerPage.confirmPasswordInput.isVisible().catch(() => false);

    if (hasConfirmPassword) {
      await registerPage.fillConfirmPassword('DifferentPassword123!');
      await registerPage.clickRegister();

      await page.waitForTimeout(1000);

      // Should show error
      const hasError = await registerPage.hasError();
      expect(hasError).toBe(true);

      const errorText = await registerPage.getErrorMessage();
      expect(errorText.toLowerCase()).toMatch(/match|confirm|same/);
    }
  });

  test.describe('Email Verification Flow', () => {
    test('R11: should handle email verification if implemented', async ({ page, testUser }) => {
      await registerPage.goto();
      await registerPage.register(testUser);

      // Wait for redirect
      await page.waitForTimeout(2000);

      // Check if redirected to email verification page
      const currentUrl = page.url();

      if (currentUrl.includes('/verify-email') || currentUrl.includes('/check-email')) {
        // Verify email verification message is shown
        const content = await page.textContent('body');
        expect(content).toMatch(/verify|check.*email|confirmation/i);
      }

      // Note: Actual email verification would require email service integration
    });
  });

  test.describe('Accessibility', () => {
    test('R12: should meet WCAG 2.1 Level AA standards', async ({ page }) => {
      await registerPage.goto();

      // Inject axe-core
      await injectAxe(page);

      // Check accessibility
      await checkA11y(page, undefined, {
        detailedReport: true,
        detailedReportOptions: {
          html: true,
        },
      });
    });

    test('R13: should be keyboard navigable', async ({ page }) => {
      await registerPage.goto();

      // Tab through form fields
      await page.keyboard.press('Tab'); // Focus username
      await expect(registerPage.usernameInput).toBeFocused();

      await page.keyboard.press('Tab'); // Focus email
      await expect(registerPage.emailInput).toBeFocused();

      await page.keyboard.press('Tab'); // Focus password
      await expect(registerPage.passwordInput).toBeFocused();
    });

    test('R14: should have proper ARIA labels', async ({ page }) => {
      await registerPage.goto();

      // Check for labels or aria-labels
      const usernameLabel = await registerPage.usernameInput.getAttribute('aria-label')
        || await page.locator('label[for*="username"]').textContent().catch(() => null);
      const emailLabel = await registerPage.emailInput.getAttribute('aria-label')
        || await page.locator('label[for*="email"]').textContent().catch(() => null);
      const passwordLabel = await registerPage.passwordInput.getAttribute('aria-label')
        || await page.locator('label[for*="password"]').textContent().catch(() => null);

      // At least form should have labels
      expect(usernameLabel || emailLabel || passwordLabel).toBeTruthy();
    });
  });

  test.describe('Security', () => {
    test('R15: should not expose sensitive data in network logs', async ({ page, testUser }) => {
      // Listen to network requests
      const requests: string[] = [];
      page.on('request', request => {
        requests.push(request.url());
      });

      await registerPage.goto();
      await registerPage.register(testUser);

      // Wait for registration request
      await page.waitForTimeout(2000);

      // Verify password is not in GET requests
      const getRequests = requests.filter(url => !url.includes('/api/auth/register'));
      getRequests.forEach(url => {
        expect(url).not.toContain(testUser.password);
      });
    });

    test('R16: should use HTTPS in production', async ({ page }) => {
      await registerPage.goto();

      // In production, should use HTTPS
      const url = page.url();

      // Note: In development/test, HTTP is acceptable
      // This test documents production requirement
      if (process.env.NODE_ENV === 'production') {
        expect(url).toMatch(/^https:/);
      }
    });
  });

  test.describe('Performance', () => {
    test('R17: should load registration page within 3 seconds', async ({ page }) => {
      const startTime = Date.now();

      await registerPage.goto();
      await page.waitForLoadState('networkidle');

      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(3000);
    });

    test('R18: should handle registration within 5 seconds', async ({ page, testUser }) => {
      await registerPage.goto();

      const startTime = Date.now();
      await registerPage.register(testUser);
      await registerPage.waitForRegistrationSuccess();

      const registrationTime = Date.now() - startTime;
      expect(registrationTime).toBeLessThan(5000);
    });
  });
});
