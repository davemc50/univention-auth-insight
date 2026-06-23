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

  const events = [];
  page.on('dialog', async (dialog) => {
    events.push({ type: 'dialog', message: dialog.message() });
    await dialog.dismiss();
  });
  page.on('response', (response) => {
    const url = response.url();
    if (url.includes('authin') || url.includes('/command/')) {
      events.push({ type: 'response', url, status: response.status() });
    }
  });
  page.on('pageerror', (err) => {
    events.push({ type: 'pageerror', text: String(err) });
  });

  await page.goto(UMC_URL, { waitUntil: 'networkidle' });
  await page.locator('input[name="username"], input#username').first().fill(UMC_USER);
  await page.locator('input[name="password"], input#password').first().fill(UMC_PASSWORD);
  await page.locator('button[type="submit"], input[type="submit"], button:has-text("Login")').first().click();
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: 'Users', exact: true }).click();
  await page.waitForTimeout(1500);

  const tile = page.locator('text=Auth Insight').first();
  console.log('tile visible', await tile.isVisible());
  await tile.click({ force: true });
  await page.waitForTimeout(3000);

  const openResult = await page.evaluate(() => {
    try {
      // eslint-disable-next-line no-undef
      const app = require('umc/app');
      const mod = app.getModule('authin');
      if (!mod) return { ok: false, error: 'getModule(authin) returned undefined' };
      app.openModule('authin');
      return { ok: true, moduleName: mod.name };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  });
  console.log('openResult', openResult);

  const instResult = await page.evaluate(() => new Promise((resolve) => {
    // eslint-disable-next-line no-undef
    require(['umc/modules/authin'], (AuthMod) => {
      try {
        const inst = new AuthMod({ moduleID: 'authin', title: 'Auth Insight', closable: true });
        inst.placeAt(document.body);
        inst.startup();
        resolve({ ok: true, subTitle: inst.subTitle });
      } catch (e) {
        resolve({ ok: false, error: String(e), stack: e.stack });
      }
    }, (err) => resolve({ ok: false, requireError: String(err) }));
  }));
  console.log('instResult', instResult);

  await page.waitForTimeout(8000);

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'debug-after-click.png'), fullPage: true });
  const body = await page.locator('body').innerText();
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'debug-after-click-body.txt'), body);
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'debug-open-events.json'), JSON.stringify(events, null, 2));

  console.log('body has Authentication logs:', body.includes('Authentication logs'));
  console.log('body has Webfrontend error:', body.includes('Webfrontend error'));
  console.log('body has 0.1.4:', body.includes('0.1.4'));
  console.log('dialogs', events.filter((e) => e.type === 'dialog'));
  console.log('authin responses', events.filter((e) => e.type === 'response' && e.url.includes('authin')));

  await browser.close();
})();
