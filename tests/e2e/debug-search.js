// SPDX-License-Identifier: AGPL-3.0-only
const fs = require('fs');
const path = require('path');
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
const ARTIFACT_DIR = path.join(__dirname, 'artifacts');

(async () => {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ ignoreHTTPSErrors: true });

  const allCommands = [];
  page.on('response', (response) => {
    const url = response.url();
    if (url.includes('/univention/command/')) {
      allCommands.push({ url, status: response.status() });
    }
  });
  page.on('dialog', async (dialog) => {
    console.log('DIALOG', dialog.message());
    await dialog.dismiss();
  });

  await page.goto(UMC_URL, { waitUntil: 'networkidle' });
  await page.locator('input[name="username"], input#username').first().fill(process.env.UMC_AUTHIN_USER);
  await page.locator('input[name="password"], input#password').first().fill(process.env.UMC_AUTHIN_PASSWORD);
  await page.locator('button[type="submit"], input[type="submit"], button:has-text("Login")').first().click();
  await page.waitForLoadState('networkidle');

  await page.evaluate(() => {
    // eslint-disable-next-line no-undef
    require('umc/app').openModule('authin');
  });
  await page.getByText(/Module debug version/, { exact: false }).waitFor({ timeout: 60000 });

  await page.evaluate(() => {
    // eslint-disable-next-line no-undef
    const tabs = require('umc/app')._tabContainer.getChildren();
    const authin = tabs.find((t) => t.moduleID === 'authin');
    if (!authin || !authin._logSearch) throw new Error('authin search form not found');
    authin._logSearch.set('value', { pattern: 'gustavo', hours: '48' });
    authin._logSearch.onSearch({ pattern: 'gustavo', hours: '48' });
  });
  await page.waitForTimeout(8000);

  const body = await page.locator('body').innerText();
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'debug-search-body.txt'), body);
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'debug-search-commands.json'), JSON.stringify(allCommands, null, 2));
  console.log('command responses', allCommands.filter((c) => c.url.includes('authin') || c.status >= 400));
  console.log('has error', body.includes('Webfrontend error'));

  await browser.close();
})();
