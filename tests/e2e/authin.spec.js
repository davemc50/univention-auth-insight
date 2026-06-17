// SPDX-License-Identifier: AGPL-3.0-only
const { test, expect } = require('@playwright/test');

const UMC_URL = process.env.UMC_AUTHIN_URL || 'https://beach.ecotegral.com/univention/management/';
const UMC_USER = process.env.UMC_AUTHIN_USER || 'Administrator';
const UMC_PASSWORD = process.env.UMC_AUTHIN_PASSWORD;

test.beforeAll(() => {
  if (!UMC_PASSWORD) {
    test.skip(true, 'UMC_AUTHIN_PASSWORD not set');
  }
});

test('Auth Insight opens and search does not show unknown request error', async ({ page }) => {
  page.on('dialog', async (dialog) => {
    const message = dialog.message();
    expect(message, 'unexpected browser dialog').not.toMatch(/unknown request/i);
    await dialog.dismiss();
  });

  await page.goto(UMC_URL, { waitUntil: 'networkidle' });

  // UCS login form (portal or UMC)
  const userField = page.locator('input[name="username"], input#username, input[type="text"]').first();
  const passField = page.locator('input[name="password"], input#password, input[type="password"]').first();
  await userField.fill(UMC_USER);
  await passField.fill(UMC_PASSWORD);
  await page.locator('button[type="submit"], input[type="submit"], button:has-text("Login")').first().click();
  await page.waitForLoadState('networkidle');

  // Open Auth Insight from Users category
  await page.getByText('Auth Insight', { exact: true }).first().click({ timeout: 60000 });
  await page.waitForTimeout(3000);

  const searchInput = page.locator('input').filter({ hasText: '' }).nth(0);
  // Search form pattern field
  await page.locator('.umcTextBox input, input[type="text"]').first().fill('gustavo');
  await page.getByRole('button', { name: /search|find/i }).first().click({ timeout: 10000 }).catch(async () => {
    await page.keyboard.press('Enter');
  });

  await page.waitForTimeout(5000);
  const body = await page.locator('body').innerText();
  expect(body).not.toMatch(/unknown request/i);
  expect(body).not.toMatch(/Webfrontend error/i);
});
