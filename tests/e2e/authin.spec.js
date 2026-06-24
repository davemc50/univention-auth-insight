// SPDX-License-Identifier: AGPL-3.0-only
const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const UMC_URL = process.env.UMC_AUTHIN_URL;
if (!UMC_URL) {
	throw new Error('UMC_AUTHIN_URL is required');
}
const UMC_USER = process.env.UMC_AUTHIN_USER || 'Administrator';
const UMC_PASSWORD = process.env.UMC_AUTHIN_PASSWORD;
const ARTIFACT_DIR = path.join(__dirname, 'artifacts');

async function loginToUmc(page) {
  await page.goto(UMC_URL, { waitUntil: 'networkidle' });

  const userField = page.locator('input[name="username"], input#username').first();
  const passField = page.locator('input[name="password"], input#password').first();
  if (await userField.isVisible({ timeout: 10000 }).catch(() => false)) {
    await userField.fill(UMC_USER);
    await passField.fill(UMC_PASSWORD);
    await page.locator('button[type="submit"], input[type="submit"], button:has-text("Login")').first().click();
    await page.waitForLoadState('networkidle');
  }
}

async function getModulesPayload(page) {
  return page.evaluate(async () => {
    const res = await fetch('/univention/get/modules', { credentials: 'include' });
    const data = await res.json();
    return data.modules || [];
  });
}

async function openAuthInsight(page) {
  const modules = await getModulesPayload(page);
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'umc-modules.json'), JSON.stringify(modules, null, 2));

  const authinModule = modules.find((mod) => mod.id === 'authin' && !mod.flavor);
  expect(
    authinModule,
    `Auth Insight is not in /get/modules for user ${UMC_USER}. ` +
    'The authin UMC policy is linked to the built-in Administrators group only — ' +
    'set UMC_AUTHIN_USER=Administrator (with that account password) in .env.e2e.'
  ).toBeTruthy();

  await page.getByRole('button', { name: 'Users', exact: true }).click();
  await page.waitForTimeout(1500);

  const opened = await page.evaluate(() => {
    // eslint-disable-next-line no-undef
    const app = require('umc/app');
    const mod = app.getModule('authin');
    if (!mod) {
      return { ok: false, error: 'getModule(authin) returned undefined' };
    }
    app.openModule('authin');
    return { ok: true, moduleName: mod.name };
  });
  expect(opened.ok, `Could not open authin module: ${opened.error || ''}`).toBe(true);

  await page.getByText(/Module debug version/, { exact: false }).waitFor({ timeout: 60000 });
  await page.waitForTimeout(2000);

  const content = await page.evaluate(() => {
    const tabs = require('umc/app')._tabContainer.getChildren();
    const authin = tabs.find((tab) => tab.moduleID === 'authin');
    const wrapper = authin && authin.domNode && authin.domNode.querySelector('.umcModuleWrapper');
    return {
      height: wrapper ? wrapper.offsetHeight : 0,
      text: wrapper ? wrapper.innerText : '',
      standingBy: authin ? authin.standingBy : null,
    };
  });
  expect(content.height, 'module content area should be visible').toBeGreaterThan(100);
  expect(content.text, 'log search help text should render').toMatch(/Search PAM/i);
  expect(content.standingBy, 'module should not be stuck on standby overlay').toBeFalsy();
}

test.beforeAll(() => {
  if (!UMC_PASSWORD) {
    test.skip(true, 'UMC_AUTHIN_PASSWORD not set');
  }
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('Auth Insight opens without frontend error on load', async ({ page }) => {
  const dialogs = [];
  const failedRequests = [];
  const authinCommands = [];

  page.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });

  page.on('requestfailed', (request) => {
    failedRequests.push({
      url: request.url(),
      failure: request.failure()?.errorText || 'unknown',
    });
  });

  page.on('response', (response) => {
    const url = response.url();
    if (url.includes('/univention/command/authin')) {
      authinCommands.push({
        url,
        status: response.status(),
      });
    }
  });

  await loginToUmc(page);
  await openAuthInsight(page);
  await page.waitForTimeout(5000);

  const body = await page.locator('body').innerText();
  const screenshotPath = path.join(ARTIFACT_DIR, 'authin-on-load.png');
  await page.screenshot({ path: screenshotPath, fullPage: true });

  if (dialogs.length) {
    fs.writeFileSync(path.join(ARTIFACT_DIR, 'dialogs.txt'), dialogs.join('\n'));
  }
  if (authinCommands.length) {
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, 'authin-commands.json'),
      JSON.stringify(authinCommands, null, 2)
    );
  }

  expect(body, 'module debug version should be visible after deploy').toMatch(/0\.1\.9/);
  expect(dialogs, `unexpected dialogs: ${dialogs.join(' | ')}`).toEqual([]);
  expect(body).not.toMatch(/unknown request/i);
  expect(body).not.toMatch(/Webfrontend error/i);
  expect(
    authinCommands.filter((entry) => entry.status === 404),
    `authin commands returned 404: ${JSON.stringify(authinCommands)}`
  ).toEqual([]);
});

test('Auth Insight opens via tile click with visible content', async ({ page }) => {
  const dialogs = [];
  page.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });

  await loginToUmc(page);
  await page.getByRole('button', { name: 'Users', exact: true }).click();
  await page.waitForTimeout(1500);
  await page.locator('text=Auth Insight').first().click({ force: true });
  await page.getByText(/Module debug version 0\.1\.9/, { exact: false }).waitFor({ timeout: 60000 });
  await page.waitForTimeout(2000);

  const content = await page.evaluate(() => {
    const tabs = require('umc/app')._tabContainer.getChildren();
    const authin = tabs.find((tab) => tab.moduleID === 'authin');
    const wrapper = authin && authin.domNode && authin.domNode.querySelector('.umcModuleWrapper');
    return {
      height: wrapper ? wrapper.offsetHeight : 0,
      text: wrapper ? wrapper.innerText : '',
      standingBy: authin ? authin.standingBy : null,
    };
  });

  expect(dialogs, `unexpected dialogs: ${dialogs.join(' | ')}`).toEqual([]);
  expect(content.height, 'tile click should render module content').toBeGreaterThan(100);
  expect(content.text).toMatch(/Search PAM/i);
  expect(content.standingBy).toBeFalsy();
});

test('Auth Insight search does not show unknown request error', async ({ page }) => {
  const dialogs = [];
  const authinCommands = [];

  page.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });

  page.on('response', (response) => {
    const url = response.url();
    if (url.includes('/univention/command/authin')) {
      authinCommands.push({
        url,
        status: response.status(),
      });
    }
  });

  await loginToUmc(page);
  await openAuthInsight(page);
  await page.waitForTimeout(3000);

  await page.evaluate(() => {
    const tabs = require('umc/app')._tabContainer.getChildren();
    const authin = tabs.find((tab) => tab.moduleID === 'authin');
    if (!authin || !authin._logSearch) {
      throw new Error('authin search form not found');
    }
    authin._logSearch.onSearch({ pattern: 'user007', hours: '48' });
  });

  await page.waitForTimeout(5000);
  const body = await page.locator('body').innerText();
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'authin-after-search.png'), fullPage: true });

  expect(dialogs, `unexpected dialogs: ${dialogs.join(' | ')}`).toEqual([]);
  expect(body).not.toMatch(/unknown request/i);
  expect(body).not.toMatch(/Webfrontend error/i);
  expect(
    authinCommands.filter((entry) => entry.url.includes('/query') && entry.status >= 400),
    `authin query failed: ${JSON.stringify(authinCommands)}`
  ).toEqual([]);
});
