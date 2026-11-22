// PW_DIR=<katalog z node_modules/playwright-core> node build/pdf.mjs [--png katalog]
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(path.join(process.env.PW_DIR || process.cwd(), 'package.json'));
const { chromium } = require('playwright-core');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pngDir = process.argv.includes('--png') ? process.argv[process.argv.indexOf('--png') + 1] : null;

const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const SRC = process.argv.includes('--src') ? process.argv[process.argv.indexOf('--src') + 1] : 'prezentacja.html';
await page.goto(pathToFileURL(path.join(root, SRC)).href + '?print');
await page.evaluate(() => document.fonts.ready);
await page.waitForLoadState('networkidle');
await page.waitForTimeout(500);

if (pngDir) {
  fs.mkdirSync(pngDir, { recursive: true });
  const n = await page.evaluate(() => document.querySelectorAll('.slide').length);
  for (let i = 0; i < n; i++) {
    const el = page.locator('.slide').nth(i);
    await el.screenshot({ path: path.join(pngDir, `slajd-${String(i).padStart(2, '0')}.png`) });
  }
  console.log('png ->', pngDir);
} else {
  const out = path.join(root, process.argv.includes('--out') ? process.argv[process.argv.indexOf('--out') + 1] : 'naladuj-mape-polski-prezentacja.pdf');
  await page.pdf({ path: out, width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true });
  console.log('pdf ->', out);
}
await browser.close();
