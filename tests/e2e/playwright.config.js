// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 120000,
  use: {
    headless: true,
    ignoreHTTPSErrors: true,
    viewport: { width: 1400, height: 900 },
  },
});
