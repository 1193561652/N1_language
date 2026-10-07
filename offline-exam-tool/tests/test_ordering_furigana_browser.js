// PLAYWRIGHT_MODULE may point to the desktop app's bundled Playwright.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    for (const year of ['2022.12', '2024.07', '2025.12']) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('dialog', d => d.accept());
      await page.goto(pathToFileURL(path.resolve(__dirname, '../../index.html')).href);
      await page.locator('#category-select').selectOption('语法');
      await page.locator('#year-select').selectOption(year);
      await page.locator('#start-button').click();
      const card = page.locator('.question-card').filter({ has: page.locator('.ordering-control') }).first();
      const choices = card.locator('[data-order-add]');
      for (let i = 0; i < 4; i++) await choices.nth(i).click();
      assert.equal(await page.locator('ruby').count(), 0);
      await card.locator('[data-check-question]').click();
      assert.equal(await page.locator('ruby').count(), 0, 'single answer reveal must not enable ruby');
      await page.locator('#submit-button').click();
      assert(await card.locator('ruby').count() > 0);
      assert(await card.locator('.order-slots ruby').count() > 0);
      const sentenceCard = page.locator('.question-card').filter({ has: page.locator('.option-list') }).first();
      assert(await sentenceCard.locator('ruby').count() > 0, 'problem 5 stems must have readings');
      assert(await page.locator('.option-list ruby').count() > 0, 'problem 5 options must have readings');
      assert.equal(await page.locator('.question-card').last().locator('ruby').count(), 0, 'problem 7 is outside scope');
      const before = await page.evaluate(() => localStorage.getItem('sbry-n1-offline-history-v1'));
      await card.locator('[data-toggle-furigana]').click();
      assert.equal(await card.locator('rt').first().evaluate(el => getComputedStyle(el).display), 'none');
      await card.locator('[data-toggle-furigana]').click();
      assert.equal(await card.locator('ruby').first().evaluate(el => getComputedStyle(el).rubyPosition), 'over');
      await page.locator('#back-button').click();
      await page.locator('[data-view="history"]').click();
      await page.locator('[data-history-id]').first().click();
      assert(await card.locator('ruby').count() > 0);
      assert.equal(await page.evaluate(() => localStorage.getItem('sbry-n1-offline-history-v1')), before);
      await page.reload();
      await page.locator('#exam-panel').waitFor({ state: 'visible' });
      assert(await card.locator('ruby').count() > 0);
      const geometry = await card.locator('ruby').first().evaluate(el => {
        const range = document.createRange(); range.selectNodeContents(el.firstChild);
        const base = range.getBoundingClientRect(), rt = el.querySelector('rt').getBoundingClientRect();
        return { baseY: base.top, rtY: rt.top, rtBottom: rt.bottom };
      });
      assert(geometry.rtY < geometry.baseY, JSON.stringify(geometry));
      if (process.env.FURIGANA_SCREENSHOT && year === '2025.12') {
        await card.screenshot({ path: process.env.FURIGANA_SCREENSHOT });
        await page.setViewportSize({ width: 390, height: 844 });
        assert(await card.evaluate(el => el.scrollWidth <= el.clientWidth + 1), 'mobile card overflow');
        await card.screenshot({ path: process.env.FURIGANA_SCREENSHOT.replace('.png', '-mobile.png') });
      }
      assert.deepEqual(errors, []);
      console.log(`PASS ${year}: submit, ruby above kanji, toggle, history, refresh, unchanged records`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
