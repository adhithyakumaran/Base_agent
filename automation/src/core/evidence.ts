import type { Page, TestInfo } from '@playwright/test';
import fs from 'fs';
import path from 'path';

export async function attachEvidence(page: Page, testInfo: TestInfo, label: string): Promise<void> {
  const screenshot = await page.screenshot({ fullPage: true });
  await testInfo.attach(`${label}-screenshot`, { body: screenshot, contentType: 'image/png' });
  const url = page.url();
  await testInfo.attach(`${label}-url`, { body: url, contentType: 'text/plain' });
}

export function evidenceDir(testInfo: TestInfo): string {
  const dir = path.join('reports', 'evidence', testInfo.titlePath.join('_'));
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}
