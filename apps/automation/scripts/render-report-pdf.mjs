#!/usr/bin/env node
/**
 * Render canonical HTML report to PDF using Playwright Chromium (Windows-friendly).
 * Usage: node render-report-pdf.mjs <html-file> <repo-root> > report.pdf
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from 'playwright';

const htmlFile = process.argv[2];
const repoRoot = path.resolve(process.argv[3] || '.');

if (!htmlFile) {
  console.error('Usage: node render-report-pdf.mjs <html-file> [repo-root]');
  process.exit(2);
}

const html = fs.readFileSync(htmlFile, 'utf8');
const automationDir = path.join(repoRoot, 'apps', 'automation');

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'load' });
  const pdf = await page.pdf({
    format: 'A4',
    printBackground: true,
    margin: { top: '18mm', bottom: '20mm', left: '16mm', right: '16mm' },
  });
  await browser.close();
  process.stdout.write(pdf);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
