import type { Page } from '@playwright/test';
import { loginUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';

export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto(loginUrl());
  }

  /** Fill credentials and submit. Waits for /home on success. */
  async login(username: string, password: string, waitForHome = true): Promise<void> {
    await performLogin(this.page, username, password);
    if (waitForHome) {
      await this.page.waitForURL(/\/home/i, { timeout: 90_000 });
    }
  }
}
