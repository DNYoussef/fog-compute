import { expect, test } from '@playwright/test';

test.describe('control panel smoke', () => {
  test('renders dashboard shell without requiring the backend', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { name: 'Fog Compute Dashboard' })).toBeVisible();
    await expect(page.getByRole('navigation')).toBeVisible();
    await expect(page.getByTestId('main-content')).toBeVisible();
  });

  test('documents backend health dependency', async ({ request }) => {
    const response = await request.get('/api/health');
    expect([200, 503]).toContain(response.status());

    const body = await response.json();
    expect(body).toHaveProperty('status');
  });
});
