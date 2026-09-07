import type { Page } from '@playwright/test';
import { loginUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';

export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto(loginUrl());
  }

  /** Fill credentials, submit, and wait for /home when waitForHome is true. */
  async login(username: string, password: string, waitForHome = true): Promise<void> {
    await performLogin(this.page, username, password);
    if (waitForHome && !/\/home/i.test(this.page.url())) {
      await this.page.waitForURL(/\/home/i, { timeout: 30_000, waitUntil: 'domcontentloaded' });
    }
  }
}
