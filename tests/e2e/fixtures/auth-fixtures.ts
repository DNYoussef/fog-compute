/**
 * Authentication Test Fixtures
 * Shared fixtures for E2E authentication tests
 */
import { test as base, expect, Page } from '@playwright/test';

/**
 * Test user data generator
 */
export function generateTestUser() {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);
  return {
    username: `e2euser${timestamp}${random}`,
    email: `e2e${timestamp}${random}@example.com`,
    password: 'TestPassword123!',
  };
}

/**
 * Authentication helper functions
 */
export class AuthHelper {
  constructor(private page: Page, private baseURL: string) {}

  /**
   * Register a new user via API
   */
  async registerUser(userData: { username: string; email: string; password: string }) {
    const response = await this.page.request.post(`${this.baseURL.replace(':3000', ':8000')}/api/auth/register`, {
      data: userData,
    });
    return response;
  }

  /**
   * Login user via API and return token
   */
  async loginUser(username: string, password: string) {
    const response = await this.page.request.post(`${this.baseURL.replace(':3000', ':8000')}/api/auth/login`, {
      data: { username, password },
    });
    if (response.ok()) {
      const data = await response.json();
      return data.access_token;
    }
    return null;
  }

  /**
   * Set authentication token in browser storage
   */
  async setAuthToken(token: string) {
    await this.page.evaluate((authToken) => {
      localStorage.setItem('access_token', authToken);
      localStorage.setItem('token_type', 'bearer');
    }, token);
  }

  /**
   * Clear authentication from browser storage
   */
  async clearAuth() {
    await this.page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('token_type');
      sessionStorage.clear();
    });
  }

  /**
   * Get current auth token from browser storage
   */
  async getAuthToken(): Promise<string | null> {
    return await this.page.evaluate(() => {
      return localStorage.getItem('access_token');
    });
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await this.getAuthToken();
    return token !== null && token !== '';
  }

  /**
   * Complete registration and login flow, return authenticated page
   */
  async authenticateUser(userData?: { username: string; email: string; password: string }) {
    const user = userData || generateTestUser();

    // Register user
    await this.registerUser(user);

    // Login and get token
    const token = await this.loginUser(user.username, user.password);

    if (!token) {
      throw new Error('Failed to authenticate user');
    }

    // Set token in browser
    await this.setAuthToken(token);

    return { user, token };
  }
}

/**
 * Extended test with auth fixtures
 */
export const test = base.extend<{
  authHelper: AuthHelper;
  authenticatedPage: Page;
  testUser: { username: string; email: string; password: string };
}>({
  /**
   * Auth helper fixture - provides authentication utilities
   */
  authHelper: async ({ page, baseURL }, use) => {
    const helper = new AuthHelper(page, baseURL || 'http://localhost:3000');
    await use(helper);
  },

  /**
   * Test user fixture - provides unique test user data
   */
  testUser: async ({}, use) => {
    await use(generateTestUser());
  },

  /**
   * Authenticated page fixture - provides a page with logged-in user
   */
  authenticatedPage: async ({ page, baseURL }, use) => {
    const helper = new AuthHelper(page, baseURL || 'http://localhost:3000');
    await helper.authenticateUser();
    await use(page);
  },
});

export { expect };
