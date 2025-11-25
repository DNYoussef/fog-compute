/**
 * Login Page Object Model
 * Encapsulates login page interactions
 */
import { Page, Locator, expect } from '@playwright/test';

export class LoginPage {
  readonly page: Page;
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly loginButton: Locator;
  readonly errorMessage: Locator;
  readonly rememberMeCheckbox: Locator;
  readonly forgotPasswordLink: Locator;
  readonly registerLink: Locator;
  readonly loginForm: Locator;

  constructor(page: Page) {
    this.page = page;

    // Locators - using data-testid for reliability
    this.loginForm = page.locator('[data-testid="login-form"]');
    this.usernameInput = page.locator('[data-testid="username-input"], input[name="username"], input[type="text"]').first();
    this.passwordInput = page.locator('[data-testid="password-input"], input[name="password"], input[type="password"]').first();
    this.loginButton = page.locator('[data-testid="login-button"], button[type="submit"]').first();
    this.errorMessage = page.locator('[data-testid="error-message"], .error-message, [role="alert"]');
    this.rememberMeCheckbox = page.locator('[data-testid="remember-me"], input[type="checkbox"][name="remember"]');
    this.forgotPasswordLink = page.locator('[data-testid="forgot-password-link"], a:has-text("Forgot")');
    this.registerLink = page.locator('[data-testid="register-link"], a:has-text("Register"), a:has-text("Sign up")');
  }

  /**
   * Navigate to login page
   */
  async goto() {
    await this.page.goto('/login');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Fill in username field
   */
  async fillUsername(username: string) {
    await this.usernameInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.usernameInput.fill(username);
  }

  /**
   * Fill in password field
   */
  async fillPassword(password: string) {
    await this.passwordInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.passwordInput.fill(password);
  }

  /**
   * Click login button
   */
  async clickLogin() {
    await this.loginButton.click();
  }

  /**
   * Toggle remember me checkbox
   */
  async toggleRememberMe() {
    await this.rememberMeCheckbox.check();
  }

  /**
   * Complete login flow
   */
  async login(username: string, password: string, rememberMe: boolean = false) {
    await this.fillUsername(username);
    await this.fillPassword(password);

    if (rememberMe) {
      await this.toggleRememberMe();
    }

    await this.clickLogin();
  }

  /**
   * Wait for successful login (redirect or dashboard visible)
   */
  async waitForLoginSuccess() {
    // Wait for either redirect or dashboard element
    await Promise.race([
      this.page.waitForURL(/\/control-panel|\/dashboard|\/home/, { timeout: 10000 }),
      this.page.locator('[data-testid="dashboard"], [data-testid="control-panel"]').waitFor({ timeout: 10000 }),
    ]);
  }

  /**
   * Get error message text
   */
  async getErrorMessage(): Promise<string> {
    await this.errorMessage.waitFor({ state: 'visible', timeout: 5000 });
    return await this.errorMessage.textContent() || '';
  }

  /**
   * Check if error message is visible
   */
  async hasError(): Promise<boolean> {
    return await this.errorMessage.isVisible();
  }

  /**
   * Verify login form is visible
   */
  async verifyFormVisible() {
    await expect(this.usernameInput).toBeVisible();
    await expect(this.passwordInput).toBeVisible();
    await expect(this.loginButton).toBeVisible();
  }

  /**
   * Get validation error for username field
   */
  async getUsernameValidationError(): Promise<string> {
    const validationMessage = await this.usernameInput.evaluate((el: HTMLInputElement) => el.validationMessage);
    return validationMessage;
  }

  /**
   * Get validation error for password field
   */
  async getPasswordValidationError(): Promise<string> {
    const validationMessage = await this.passwordInput.evaluate((el: HTMLInputElement) => el.validationMessage);
    return validationMessage;
  }
}
