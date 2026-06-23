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
  const page = await browser.newPage({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 } });

  const errors = [];
  page.on('pageerror', (err) => errors.push({ type: 'pageerror', text: String(err), stack: err.stack }));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push({ type: 'console', text: msg.text() });
  });

  await page.goto(UMC_URL, { waitUntil: 'networkidle' });
  const uf = page.locator('input[name="username"], input#username').first();
  if (await uf.isVisible({ timeout: 10000 }).catch(() => false)) {
    await uf.fill(process.env.UMC_AUTHIN_USER);
    await page.locator('input[name="password"], input#password').first().fill(process.env.UMC_AUTHIN_PASSWORD);
    await page.locator('button[type="submit"], input[type="submit"], button:has-text("Login")').first().click();
    await page.waitForLoadState('networkidle');
  }

  // Real user path: Users category, click tile
  await page.getByRole('button', { name: 'Users', exact: true }).click();
  await page.waitForTimeout(1500);
  await page.locator('text=Auth Insight').first().click({ force: true });
  await page.waitForTimeout(8000);

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'blackscreen-tile-click.png'), fullPage: true });

  const body = await page.locator('body').innerText();
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'blackscreen-body.txt'), body);
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'blackscreen-errors.json'), JSON.stringify(errors, null, 2));

  const metrics = await page.evaluate(() => {
    const tabs = require('umc/app')._tabContainer.getChildren();
    const authin = tabs.find((t) => t.moduleID === 'authin');
    const moduleNode = authin && authin.domNode;
    const content = moduleNode && moduleNode.querySelector('.umcModuleWrapper');
    return {
      tabCount: tabs.length,
      hasAuthinTab: !!authin,
      moduleDisplay: moduleNode ? getComputedStyle(moduleNode).display : null,
      contentHeight: content ? content.offsetHeight : null,
      contentText: content ? content.innerText.slice(0, 500) : null,
      subTitle: authin && authin.subTitle,
      hasLogSearch: !!(authin && authin._logSearch),
      hasLogGrid: !!(authin && authin._logGrid),
    };
  });

  console.log('metrics', JSON.stringify(metrics, null, 2));
  console.log('body has Search field:', body.includes('Search PAM'));
  console.log('body has debug version:', body.includes('0.1.9'));
  console.log('errors', errors.filter((e) => !e.text.includes('piwik') && !e.text.includes('401')).slice(0, 5));

  await browser.close();
})();
