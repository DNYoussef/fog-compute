import { expect, Locator, Page } from '@playwright/test';

async function isVisible(locator: Locator, timeout = 750): Promise<boolean> {
  return locator.isVisible({ timeout }).catch(() => false);
}

export async function openMobileMenu(page: Page): Promise<boolean> {
  const drawer = page.locator('[data-testid="mobile-menu-drawer"]').first();
  if (await isVisible(drawer)) {
    return true;
  }

  const menuButton = page.locator('[data-testid="mobile-menu-button"]:visible').first();

  if (!(await isVisible(menuButton))) {
    return false;
  }

  await menuButton.click();
  await expect(drawer).toBeVisible();
  return true;
}

export async function expectPrimaryNavRoute(page: Page, route: string): Promise<void> {
  const desktopNav = page.locator('[data-testid="desktop-nav"]:visible').first();

  if (await isVisible(desktopNav)) {
    await expect(desktopNav.locator(`[data-testid$="-link"][href="${route}"]`)).toBeVisible();
    return;
  }

  await openMobileMenu(page);
  await expect(
    page.locator(`[data-testid="mobile-menu-drawer"] [data-testid="menu-item"][data-route="${route}"]`)
  ).toBeVisible();
}

export async function visibleWebSocketStatus(page: Page): Promise<Locator> {
  const desktopStatus = page.locator('[data-testid="ws-status"]:visible').first();

  if (await isVisible(desktopStatus)) {
    return desktopStatus;
  }

  await openMobileMenu(page);
  return page.locator('[data-testid="mobile-ws-status"]:visible').first();
}
