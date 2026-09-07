import type { Page } from '@playwright/test';
import { appPath, appUrl, homeUrl, loginUrl } from '../core/app-url';

/** Prefer absolute URLs for auth entry points. */
export async function gotoLogin(page: Page): Promise<void> {
  await page.goto(loginUrl());
}

/** Navigate within the EA app using a safe relative path (./segment). */
export async function gotoApp(page: Page, pathSegment: string): Promise<void> {
  await page.goto(appPath(pathSegment));
}

/** Navigate using a fully resolved app URL. */
export async function gotoAppUrl(page: Page, pathSegment: string): Promise<void> {
  await page.goto(appUrl(pathSegment));
}

export async function gotoHome(page: Page): Promise<void> {
  await page.goto(homeUrl());
}

export { appPath, appUrl, homeUrl, loginUrl };
