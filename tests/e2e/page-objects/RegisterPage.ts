/**
 * Registration Page Object Model
 * Encapsulates registration page interactions
 */
import { Page, Locator, expect } from '@playwright/test';

export class RegisterPage {
  readonly page: Page;
  readonly usernameInput: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly confirmPasswordInput: Locator;
  readonly registerButton: Locator;
  readonly errorMessage: Locator;
  readonly successMessage: Locator;
  readonly loginLink: Locator;
  readonly registerForm: Locator;
  readonly passwordStrengthIndicator: Locator;
  readonly termsCheckbox: Locator;

  constructor(page: Page) {
    this.page = page;

    // Locators - using data-testid and fallbacks
    this.registerForm = page.locator('[data-testid="register-form"]');
    this.usernameInput = page.locator('[data-testid="username-input"], input[name="username"]').first();
    this.emailInput = page.locator('[data-testid="email-input"], input[name="email"], input[type="email"]').first();
    this.passwordInput = page.locator('[data-testid="password-input"], input[name="password"]').first();
    this.confirmPasswordInput = page.locator('[data-testid="confirm-password-input"], input[name="confirmPassword"]');
    this.registerButton = page.locator('[data-testid="register-button"], button[type="submit"]').first();
    this.errorMessage = page.locator('[data-testid="error-message"], .error-message, [role="alert"]');
    this.successMessage = page.locator('[data-testid="success-message"], .success-message');
    this.loginLink = page.locator('[data-testid="login-link"], a:has-text("Login"), a:has-text("Sign in")');
    this.passwordStrengthIndicator = page.locator('[data-testid="password-strength"], .password-strength');
    this.termsCheckbox = page.locator('[data-testid="terms-checkbox"], input[type="checkbox"][name="terms"]');
  }

  /**
   * Navigate to registration page
   */
  async goto() {
    await this.page.goto('/register');
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
   * Fill in email field
   */
  async fillEmail(email: string) {
    await this.emailInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.emailInput.fill(email);
  }

  /**
   * Fill in password field
   */
  async fillPassword(password: string) {
    await this.passwordInput.waitFor({ state: 'visible', timeout: 5000 });
    await this.passwordInput.fill(password);
  }

  /**
   * Fill in confirm password field (if exists)
   */
  async fillConfirmPassword(password: string) {
    const isVisible = await this.confirmPasswordInput.isVisible().catch(() => false);
    if (isVisible) {
      await this.confirmPasswordInput.fill(password);
    }
  }

  /**
   * Click register button
   */
  async clickRegister() {
    await this.registerButton.click();
  }

  /**
   * Accept terms and conditions (if exists)
   */
  async acceptTerms() {
    const isVisible = await this.termsCheckbox.isVisible().catch(() => false);
    if (isVisible) {
      await this.termsCheckbox.check();
    }
  }

  /**
   * Complete registration flow
   */
  async register(userData: { username: string; email: string; password: string }, acceptTerms: boolean = true) {
    await this.fillUsername(userData.username);
    await this.fillEmail(userData.email);
    await this.fillPassword(userData.password);
    await this.fillConfirmPassword(userData.password);

    if (acceptTerms) {
      await this.acceptTerms();
    }

    await this.clickRegister();
  }

  /**
   * Wait for successful registration (redirect or success message)
   */
  async waitForRegistrationSuccess() {
    await Promise.race([
      this.page.waitForURL(/\/login|\/verify-email|\/control-panel/, { timeout: 10000 }),
      this.successMessage.waitFor({ state: 'visible', timeout: 10000 }),
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
   * Get password strength indicator text
   */
  async getPasswordStrength(): Promise<string> {
    const isVisible = await this.passwordStrengthIndicator.isVisible().catch(() => false);
    if (isVisible) {
      return await this.passwordStrengthIndicator.textContent() || '';
    }
    return '';
  }

  /**
   * Verify registration form is visible
   */
  async verifyFormVisible() {
    await expect(this.usernameInput).toBeVisible();
    await expect(this.emailInput).toBeVisible();
    await expect(this.passwordInput).toBeVisible();
    await expect(this.registerButton).toBeVisible();
  }

  /**
   * Get field-specific validation error
   */
  async getFieldValidationError(field: 'username' | 'email' | 'password'): Promise<string> {
    const locator = field === 'username' ? this.usernameInput :
                    field === 'email' ? this.emailInput :
                    this.passwordInput;

    const validationMessage = await locator.evaluate((el: HTMLInputElement) => el.validationMessage);
    return validationMessage;
  }

  /**
   * Check if email field shows invalid state
   */
  async isEmailInvalid(): Promise<boolean> {
    return await this.emailInput.evaluate((el: HTMLInputElement) => !el.validity.valid);
  }
}
