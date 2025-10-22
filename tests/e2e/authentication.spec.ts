import { test, expect } from '@playwright/test';

/**
 * Authentication E2E Tests
 * Tests user registration, login, protected routes, and JWT token handling
 */

test.describe('Authentication Flow', () => {
  const timestamp = Date.now();
  const testUser = {
    username: `e2euser${timestamp}`,
    email: `e2e${timestamp}@example.com`,
    password: 'TestPassword123'
  };

  test('should register a new user', async ({ page }) => {
    // Navigate to registration page (when it exists)
    await page.goto('/');

    // For now, test the API directly
    const response = await page.request.post('http://localhost:8000/api/auth/register', {
      data: testUser
    });

    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(201);

    const data = await response.json();
    expect(data.username).toBe(testUser.username);
    expect(data.email).toBe(testUser.email);
    expect(data.is_active).toBe(true);
    expect(data).not.toHaveProperty('hashed_password');
  });

  test('should login with valid credentials', async ({ page }) => {
    // First register
    await page.request.post('http://localhost:8000/api/auth/register', {
      data: testUser
    });

    // Then login
    const response = await page.request.post('http://localhost:8000/api/auth/login', {
      data: {
        username: testUser.username,
        password: testUser.password
      }
    });

    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('access_token');
    expect(data.token_type).toBe('bearer');
    expect(data.expires_in).toBe(1800); // 30 minutes
  });

  test('should reject invalid login credentials', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/api/auth/login', {
      data: {
        username: 'nonexistent',
        password: 'wrong'
      }
    });

    expect(response.status()).toBe(401);
  });

  test('should access protected endpoint with valid token', async ({ page }) => {
    // Register and login
    await page.request.post('http://localhost:8000/api/auth/register', {
      data: testUser
    });

    const loginResponse = await page.request.post('http://localhost:8000/api/auth/login', {
      data: {
        username: testUser.username,
        password: testUser.password
      }
    });

    const { access_token } = await loginResponse.json();

    // Access protected endpoint
    const response = await page.request.get('http://localhost:8000/api/auth/me', {
      headers: {
        'Authorization': `Bearer ${access_token}`
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.username).toBe(testUser.username);
  });

  test('should reject access to protected endpoint without token', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/api/auth/me');
    expect(response.status()).toBe(403);
  });

  test('should reject access with invalid token', async ({ page }) => {
    const response = await page.request.get('http://localhost:8000/api/auth/me', {
      headers: {
        'Authorization': 'Bearer invalid_token_12345'
      }
    });

    expect(response.status()).toBe(401);
  });

  test('should enforce password complexity requirements', async ({ page }) => {
    // No uppercase
    let response = await page.request.post('http://localhost:8000/api/auth/register', {
      data: {
        username: `weak${timestamp}`,
        email: `weak${timestamp}@example.com`,
        password: 'weakpassword123'
      }
    });
    expect(response.status()).toBe(422);

    // No numbers
    response = await page.request.post('http://localhost:8000/api/auth/register', {
      data: {
        username: `weak2${timestamp}`,
        email: `weak2${timestamp}@example.com`,
        password: 'WeakPassword'
      }
    });
    expect(response.status()).toBe(422);

    // No lowercase
    response = await page.request.post('http://localhost:8000/api/auth/register', {
      data: {
        username: `weak3${timestamp}`,
        email: `weak3${timestamp}@example.com`,
        password: 'WEAKPASSWORD123'
      }
    });
    expect(response.status()).toBe(422);
  });

  test('should reject duplicate usernames', async ({ page }) => {
    // Register first time
    await page.request.post('http://localhost:8000/api/auth/register', {
      data: testUser
    });

    // Try to register again
    const response = await page.request.post('http://localhost:8000/api/auth/register', {
      data: testUser
    });

    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.detail).toContain('already registered');
  });

  test('should enforce rate limiting on auth endpoints', async ({ page }) => {
    let rateLimitHit = false;

    // Make 15 login attempts
    for (let i = 0; i < 15; i++) {
      const response = await page.request.post('http://localhost:8000/api/auth/login', {
        data: {
          username: 'nonexistent',
          password: 'wrong'
        }
      });

      if (response.status() === 429) {
        rateLimitHit = true;
        const data = await response.json();
        expect(data.error).toContain('Rate limit exceeded');
        expect(data).toHaveProperty('retry_after');
        break;
      }
    }

    expect(rateLimitHit).toBeTruthy();
  });

  test('should logout successfully', async ({ page }) => {
    // Register and login
    await page.request.post('http://localhost:8000/api/auth/register', {
      data: testUser
    });

    const loginResponse = await page.request.post('http://localhost:8000/api/auth/login', {
      data: {
        username: testUser.username,
        password: testUser.password
      }
    });

    const { access_token } = await loginResponse.json();

    // Logout
    const response = await page.request.post('http://localhost:8000/api/auth/logout', {
      headers: {
        'Authorization': `Bearer ${access_token}`
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.message).toContain('Successfully logged out');
  });
});

test.describe('Authentication UI Integration', () => {
  test.skip('should display login form', async ({ page }) => {
    // TODO: Implement when login UI is created
    await page.goto('/login');
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
    await expect(page.locator('[data-testid="username-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="login-button"]')).toBeVisible();
  });

  test.skip('should display registration form', async ({ page }) => {
    // TODO: Implement when registration UI is created
    await page.goto('/register');
    await expect(page.locator('[data-testid="register-form"]')).toBeVisible();
    await expect(page.locator('[data-testid="username-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="email-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="register-button"]')).toBeVisible();
  });

  test.skip('should redirect to login for protected routes', async ({ page }) => {
    // TODO: Implement when route protection is added to frontend
    await page.goto('/control-panel');
    await expect(page).toHaveURL(/\/login/);
  });
});
