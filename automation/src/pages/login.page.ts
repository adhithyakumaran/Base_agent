import type { Page } from '@playwright/test';
import { loginUrl } from '../core/app-url';
import { performLogin } from '../core/login-setup';

export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto(loginUrl());
  }

  async login(username: string, password: string): Promise<void> {
    await performLogin(this.page, username, password);
  }
}
