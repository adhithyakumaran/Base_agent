import type { Page } from '@playwright/test';
import { LOCATORS, LocatorResolver } from '../core/locator-chain';

export class LoginPage {
  private readonly resolver: LocatorResolver;

  constructor(private readonly page: Page) {
    this.resolver = new LocatorResolver(page);
  }

  async goto(): Promise<void> {
    const loginPath = process.env.EA_LOGIN_URL ?? '/login';
    await this.page.goto(loginPath);
  }

  async login(username: string, password: string): Promise<void> {
    const user = await this.resolver.resolve([...LOCATORS.login.username], 'username');
    const pass = await this.resolver.resolve([...LOCATORS.login.password], 'password');
    const submit = await this.resolver.resolve([...LOCATORS.login.submit], 'login submit');
    await user.fill(username);
    await pass.fill(password);
    await submit.click();
  }
}
