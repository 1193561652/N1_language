const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    for (const year of ['2022.12', '2024.07', '2025.12']) {
      const context = await browser.newContext();
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('dialog', d => d.accept());
      await page.goto(pathToFileURL(path.resolve(__dirname, '../../index.html')).href);
      await page.locator('#category-select').selectOption('阅读');
      await page.locator('#year-select').selectOption(year);
      await page.locator('#start-button').click();
      const card = page.locator('.question-card').first();
      assert.equal(await page.locator('ruby').count(), 0);
      await card.locator('[data-check-question]').click();
      assert.equal(await page.locator('ruby').count(), 0);
      await page.locator('#submit-button').click();
      assert(await card.locator('ruby').count() > 0);
      assert(await page.locator('.option-list ruby').count() > 0);
      assert(await page.locator('[data-toggle-furigana]').count() > 0);
      await card.locator('[data-toggle-furigana]').click();
      assert.notEqual(await card.locator('rt').first().evaluate(el => getComputedStyle(el).display), 'none');
      await card.locator('[data-toggle-furigana]').click();
      assert.equal(await card.locator('rt').first().evaluate(el => getComputedStyle(el).display), 'none');
      await page.locator('#back-button').click();
      await page.locator('[data-view="history"]').click();
      await page.locator('[data-history-id]').first().click();
      assert(await card.locator('ruby').count() > 0);
      await page.reload();
      await page.locator('#exam-panel').waitFor({ state: 'visible' });
      assert(await card.locator('ruby').count() > 0);
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log('PASS: reading furigana submission, options, toggle, history and reload across three sources');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
