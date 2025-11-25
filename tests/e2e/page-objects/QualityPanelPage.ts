/**
 * Quality Panel Page Object Model
 * Encapsulates TestExecutionPanel/Quality Panel interactions
 */
import { Page, Locator, expect } from '@playwright/test';

export class QualityPanelPage {
  readonly page: Page;
  readonly panel: Locator;
  readonly panelTitle: Locator;
  readonly testSuiteDropdown: Locator;
  readonly runTestsButton: Locator;
  readonly runBenchmarksButton: Locator;
  readonly rustQuickButton: Locator;
  readonly pythonQuickButton: Locator;
  readonly integrationQuickButton: Locator;
  readonly e2eQuickButton: Locator;
  readonly consoleOutput: Locator;
  readonly clearButton: Locator;
  readonly loadingIndicator: Locator;
  readonly testCommandsDetails: Locator;
  readonly errorMessages: Locator;

  constructor(page: Page) {
    this.page = page;

    // Main panel locators
    this.panel = page.locator('.glass.rounded-xl').filter({ hasText: 'Test Execution' }).first();
    this.panelTitle = page.locator('h2').filter({ hasText: 'Test Execution' });

    // Control elements
    this.testSuiteDropdown = page.locator('select').first();
    this.runTestsButton = page.locator('button').filter({ hasText: /Run Tests/i }).first();
    this.runBenchmarksButton = page.locator('button').filter({ hasText: /Run Benchmarks/i }).first();

    // Quick action buttons
    this.rustQuickButton = page.locator('button').filter({ hasText: 'Rust' });
    this.pythonQuickButton = page.locator('button').filter({ hasText: 'Python' });
    this.integrationQuickButton = page.locator('button').filter({ hasText: 'Integration' });
    this.e2eQuickButton = page.locator('button').filter({ hasText: 'E2E' });

    // Console and status elements
    this.consoleOutput = page.locator('.bg-black\\/50.rounded-lg').first();
    this.clearButton = page.locator('button').filter({ hasText: 'Clear' });
    this.loadingIndicator = page.locator('.animate-spin, .animate-pulse');
    this.testCommandsDetails = page.locator('details');

    // Error elements
    this.errorMessages = page.locator('.text-red-400, [role="alert"]');
  }

  /**
   * Navigate to control panel with quality panel
   */
  async goto() {
    await this.page.goto('/control-panel');
    await this.page.waitForLoadState('networkidle');
    await this.panel.waitFor({ state: 'visible', timeout: 10000 });
  }

  /**
   * Select test suite from dropdown
   */
  async selectTestSuite(suite: 'all' | 'rust' | 'python') {
    await this.testSuiteDropdown.selectOption(suite);
    await this.page.waitForTimeout(500); // Debounce
  }

  /**
   * Click run tests button
   */
  async clickRunTests() {
    await this.runTestsButton.click();
  }

  /**
   * Click run benchmarks button
   */
  async clickRunBenchmarks() {
    await this.runBenchmarksButton.click();
  }

  /**
   * Click quick action button
   */
  async clickQuickAction(action: 'rust' | 'python' | 'integration' | 'e2e') {
    const buttonMap = {
      rust: this.rustQuickButton,
      python: this.pythonQuickButton,
      integration: this.integrationQuickButton,
      e2e: this.e2eQuickButton,
    };
    await buttonMap[action].click();
  }

  /**
   * Wait for test execution to start
   */
  async waitForTestsToStart() {
    await this.loadingIndicator.waitFor({ state: 'visible', timeout: 5000 });
  }

  /**
   * Wait for test execution to complete
   */
  async waitForTestsToComplete(timeout: number = 60000) {
    // Wait for loading indicator to disappear
    await this.loadingIndicator.waitFor({ state: 'hidden', timeout });

    // Wait for button to be enabled again
    await expect(this.runTestsButton).toBeEnabled({ timeout: 5000 });
  }

  /**
   * Get console output text
   */
  async getConsoleOutput(): Promise<string> {
    const output = await this.consoleOutput.textContent();
    return output || '';
  }

  /**
   * Get console output lines as array
   */
  async getConsoleOutputLines(): Promise<string[]> {
    const lines = await this.consoleOutput.locator('div').allTextContents();
    return lines.filter(line => line.trim().length > 0);
  }

  /**
   * Check if console has output
   */
  async hasConsoleOutput(): Promise<boolean> {
    const output = await this.getConsoleOutput();
    return output.length > 0 && !output.includes('No output yet');
  }

  /**
   * Clear console output
   */
  async clearConsole() {
    await this.clearButton.click();
    await this.page.waitForTimeout(1000); // Wait for reload
  }

  /**
   * Check if tests are running
   */
  async isRunning(): Promise<boolean> {
    return await this.loadingIndicator.isVisible();
  }

  /**
   * Check if test suite dropdown is disabled
   */
  async isDropdownDisabled(): Promise<boolean> {
    return await this.testSuiteDropdown.isDisabled();
  }

  /**
   * Check if run buttons are disabled
   */
  async areButtonsDisabled(): Promise<boolean> {
    const testButtonDisabled = await this.runTestsButton.isDisabled();
    const benchmarkButtonDisabled = await this.runBenchmarksButton.isDisabled();
    return testButtonDisabled && benchmarkButtonDisabled;
  }

  /**
   * Expand test commands details
   */
  async expandTestCommands() {
    if (!await this.testCommandsDetails.locator('summary').getAttribute('open')) {
      await this.testCommandsDetails.click();
    }
  }

  /**
   * Get test commands text
   */
  async getTestCommands(): Promise<string> {
    await this.expandTestCommands();
    return await this.testCommandsDetails.textContent() || '';
  }

  /**
   * Count success/fail/warning messages in output
   */
  async countOutputMessages(): Promise<{ success: number; fail: number; warn: number }> {
    const lines = await this.getConsoleOutputLines();

    return {
      success: lines.filter(line =>
        line.includes('PASS') || line.includes('OK') || line.includes('\u2713')
      ).length,
      fail: lines.filter(line =>
        line.includes('FAIL') || line.includes('ERROR') || line.includes('\u2717')
      ).length,
      warn: lines.filter(line =>
        line.includes('WARN')
      ).length,
    };
  }

  /**
   * Verify panel is visible and loaded
   */
  async verifyPanelVisible() {
    await expect(this.panel).toBeVisible();
    await expect(this.panelTitle).toBeVisible();
    await expect(this.testSuiteDropdown).toBeVisible();
    await expect(this.runTestsButton).toBeVisible();
    await expect(this.runBenchmarksButton).toBeVisible();
  }

  /**
   * Verify quick action buttons are visible
   */
  async verifyQuickActionsVisible() {
    await expect(this.rustQuickButton).toBeVisible();
    await expect(this.pythonQuickButton).toBeVisible();
    await expect(this.integrationQuickButton).toBeVisible();
    await expect(this.e2eQuickButton).toBeVisible();
  }

  /**
   * Verify console output section
   */
  async verifyConsoleVisible() {
    await expect(this.consoleOutput).toBeVisible();
    await expect(this.clearButton).toBeVisible();
  }

  /**
   * Get error messages
   */
  async getErrorMessages(): Promise<string[]> {
    const errors = await this.errorMessages.allTextContents();
    return errors.filter(err => err.trim().length > 0);
  }

  /**
   * Check for specific output pattern
   */
  async hasOutputPattern(pattern: RegExp): Promise<boolean> {
    const output = await this.getConsoleOutput();
    return pattern.test(output);
  }

  /**
   * Wait for specific output text
   */
  async waitForOutputText(text: string, timeout: number = 30000) {
    await this.page.waitForFunction(
      (searchText) => {
        const console = document.querySelector('.bg-black\\/50.rounded-lg');
        return console?.textContent?.includes(searchText) || false;
      },
      text,
      { timeout }
    );
  }

  /**
   * Trigger keyboard navigation for accessibility
   */
  async navigateWithKeyboard() {
    // Tab through interactive elements
    await this.page.keyboard.press('Tab'); // Test suite dropdown
    await this.page.keyboard.press('Tab'); // Run tests button
    await this.page.keyboard.press('Tab'); // Run benchmarks button

    // Check focus is visible
    const focusedElement = await this.page.evaluateHandle(() => document.activeElement);
    return focusedElement;
  }

  /**
   * Get ARIA labels for accessibility testing
   */
  async getAriaLabels(): Promise<Record<string, string | null>> {
    return {
      panel: await this.panel.getAttribute('aria-label'),
      runTests: await this.runTestsButton.getAttribute('aria-label'),
      runBenchmarks: await this.runBenchmarksButton.getAttribute('aria-label'),
      console: await this.consoleOutput.getAttribute('aria-label'),
    };
  }
}
