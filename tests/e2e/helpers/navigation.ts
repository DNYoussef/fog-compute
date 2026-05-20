import type { Page, Response } from '@playwright/test';

function isRetriableNavigationError(error: unknown) {
  const message = String(error);

  return (
    message.includes('NS_ERROR_SOCKET_ADDRESS_IN_USE') ||
    message.includes('net::ERR_SOCKET_NOT_CONNECTED') ||
    message.includes('net::ERR_CONNECTION_RESET')
  );
}

export async function gotoWithRetries(
  page: Page,
  url: string,
  options?: Parameters<Page['goto']>[1],
): Promise<Response | null> {
  let lastError: unknown;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await page.goto(url, options);
    } catch (error) {
      const message = String(error);

      if (message.includes('interrupted by another navigation')) {
        return null;
      }

      lastError = error;

      if (!isRetriableNavigationError(error) || attempt === 2) {
        throw error;
      }

      await page.waitForTimeout(250 * (attempt + 1));
      await page.goto('about:blank', { waitUntil: 'domcontentloaded', timeout: 5000 }).catch(() => {});
    }
  }

  throw lastError;
}
