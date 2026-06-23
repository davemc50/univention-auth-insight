// SPDX-License-Identifier: AGPL-3.0-only
// One-off debug: login, dump module list from UMC API, try opening authin.
const fs = require('fs');
const path = require('path');
require('@playwright/test');
const { chromium } = require('@playwright/test');

const ROOT = path.join(__dirname, '..', '..');
const envPath = path.join(ROOT, '.env.e2e');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const idx = trimmed.indexOf('=');
    const key = trimmed.slice(0, idx);
    let value = trimmed.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) process.env[key] = value;
  }
}

const UMC_URL = process.env.UMC_AUTHIN_URL;
if (!UMC_URL) {
	throw new Error('UMC_AUTHIN_URL is required');
}
const UMC_USER = process.env.UMC_AUTHIN_USER || 'Administrator';
const UMC_PASSWORD = process.env.UMC_AUTHIN_PASSWORD;
const ARTIFACT_DIR = path.join(__dirname, 'artifacts');

(async () => {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ ignoreHTTPSErrors: true });

  const moduleResponses = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/univention/')) {
      let body = null;
      try {
        body = await response.json();
      } catch (e) {
        body = null;
      }
      moduleResponses.push({ url, status: response.status(), body });
    }
  });

  await page.goto(UMC_URL, { waitUntil: 'networkidle' });
  const userField = page.locator('input[name="username"], input#username, input[type="text"]').first();
  if (await userField.isVisible({ timeout: 5000 }).catch(() => false)) {
    await userField.fill(UMC_USER);
    await page.locator('input[name="password"], input#password, input[type="password"]').first().fill(UMC_PASSWORD);
    await page.locator('button[type="submit"], input[type="submit"], button:has-text("Login")').first().click();
    await page.waitForLoadState('networkidle');
  }

  await page.getByRole('button', { name: 'Users', exact: true }).click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'debug-users-tab.png'), fullPage: true });

  const bodyText = await page.locator('body').innerText();
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'debug-users-body.txt'), bodyText);
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'debug-module-responses.json'), JSON.stringify(moduleResponses, null, 2));

  const authinTile = page.getByText('Auth Insight', { exact: true });
  console.log('Auth Insight visible:', await authinTile.isVisible().catch(() => false));
  console.log('Body mentions Auth Insight:', bodyText.includes('Auth Insight'));
  console.log('Captured responses:', moduleResponses.map((r) => r.url));

  await browser.close();
})();
