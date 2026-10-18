// Invoked by test_cafe_release_acceptance.py against a disposable PostgreSQL DB.
const { chromium, expect } = require(process.env.CAFE_PLAYWRIGHT_MODULE || '@playwright/test');
const { execFileSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const artifacts = process.env.CAFE_AUDIT_ARTIFACTS;
const snapshot = () => execFileSync(process.env.CAFE_AUDIT_PYTHON,
  [path.join(root, 'backend/tests/cafe_acceptance_snapshot.py')], { encoding: 'utf8' }).trim();
const rows = (state, table) => JSON.parse(state)[table].map(JSON.parse);
const totp = () => execFileSync(process.env.CAFE_AUDIT_PYTHON,
  ['-c', 'import os,pyotp;print(pyotp.TOTP(os.environ["CAFE_AUDIT_TOTP"]).now())'], { encoding: 'utf8' }).trim();
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date());

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [], outbound = [], checkoutRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  // Simulate loss of internet while preserving local LAN/loopback access.
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      outbound.push(url.hostname); return route.abort('internetdisconnected');
    }
    if (url.pathname === '/api/cafe/billing/pos/checkout' && route.request().method() === 'POST') checkoutRequests.push({
      body: route.request().postDataJSON(), key: await route.request().headerValue('idempotency-key'),
    });
    return route.continue();
  });
  const login = async owner => {
    await page.getByLabel('Email', { exact: true }).fill(owner ? 'owner@example.com' : 'cashier@example.com');
    await page.getByLabel('Password', { exact: true }).fill(owner ? 'ActualAdmin-Secret123!' : 'ActualCashier-Secret456!');
    if (owner) await page.getByLabel('Authenticator code', { exact: true }).fill(totp());
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page).toHaveURL(owner ? /\/cafe\/dashboard$/ : /\/cafe\/pos$/);
  };
  const logout = async () => {
    await page.getByRole('button', { name: 'Logout', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
  };
  const metric = (label) => page.locator('.metric-card').filter({ has: page.getByText(label, { exact: true }) }).locator('strong');
  const api = (url, method = 'GET', body, extraHeaders = {}) => page.evaluate(async ({ url, method, body, extraHeaders }) => {
    const response = await fetch(`http://127.0.0.1:8000/api${url}`, {
      method, headers: { Authorization: `Bearer ${sessionStorage.getItem('hybrid_retail_auth_token')}`, 'Content-Type': 'application/json', ...extraHeaders },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    return { status: response.status, body: await response.json() };
  }, { url, method, body, extraHeaders });
  try {
    await page.goto('http://127.0.0.1:4173/');
    await login(true);
    await page.getByRole('button', { name: 'Daily Closing', exact: true }).click();
    if (process.argv[2] === 'operations') {
      await page.getByLabel('Opening cash', { exact: true }).fill('100');
      await page.getByRole('button', { name: 'Open business day', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Status: open', exact: true })).toBeVisible();
      await logout();
      await login(false);
      await expect(page.getByRole('button', { name: 'Inventory', exact: true })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Daily Closing', exact: true })).toHaveCount(0);
      expect((await api('/dashboard/cafe')).status).toBe(403);
      // A direct owner URL must not bypass employee routing.
      await page.goto('http://127.0.0.1:4173/cafe/inventory');
      await expect(page).toHaveURL(/\/cafe\/pos$/);
      expect(await page.evaluate(() => fetch('https://offline.invalid/probe').then(() => false).catch(() => true))).toBe(true);
      const invoices = [];
      for (const [index, [mode, quantity, orderType]] of [
        ['Cash', 2, 'counter'], ['UPI', 1, 'takeaway'], ['Card', 3, 'counter'], ['Cash', 1, 'takeaway'],
      ].entries()) {
        await page.getByLabel('Search menu', { exact: true }).fill('Sandwich');
        await page.locator('.cafe-pos-menu button').filter({ hasText: 'Audit Sandwich' }).click();
        for (let i = 1; i < quantity; i++) await page.getByRole('button', { name: 'Add one Audit Sandwich', exact: true }).click();
        await page.getByRole('combobox', { name: /^Order/ }).selectOption(orderType);
        await page.getByRole('combobox', { name: /^Payment/ }).selectOption({ label: mode });
        if (mode !== 'Cash') await page.getByLabel('Payment reference', { exact: true }).fill(`AUDIT-${mode}-${index}`);
        const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/cafe/billing/pos/checkout') && response.request().method() === 'POST');
        await page.getByRole('button', { name: 'Pay & create invoice', exact: true }).click({ clickCount: 2 });
        const response = await responsePromise;
        expect(response.status()).toBe(200);
        const result = await response.json();
        invoices.push(result.receipt.invoice_number);
        await expect(page.getByRole('button', { name: 'Print receipt', exact: true })).toBeVisible();
        expect(checkoutRequests).toHaveLength(index + 1);
        expect(Number(result.receipt.grand_total)).toBe(quantity * 100);
        expect(result.receipt.cafe_name).toBe('Real Configured Cafe');
        expect(result.receipt.branch_name).toBe('Main Counter');
        expect(Number(result.receipt.paid_amount)).toBe(quantity * 100);
        const beforeReplay = snapshot(), attempt = checkoutRequests[index];
        const replay = await api('/cafe/billing/pos/checkout', 'POST', attempt.body, { 'Idempotency-Key': attempt.key });
        expect(replay.status).toBe(200); expect(replay.body.idempotent_replay).toBe(true);
        expect(snapshot()).toBe(beforeReplay);
        // Exclude explicit network replay probes when counting later UI submits.
        checkoutRequests.pop();
        await page.evaluate(() => { window.print = () => window.dispatchEvent(new Event('beforeprint')); });
        await page.getByRole('button', { name: 'Print receipt', exact: true }).click();
        await page.emulateMedia({ media: 'print' });
        await expect(page.locator('#root')).toBeHidden();
        const paper = page.locator('#cafe-receipt-print-root');
        for (const text of ['Real Configured Cafe', 'Main Counter', result.receipt.invoice_number, 'Audit Sandwich', mode, 'Grand total', 'Amount paid']) await expect(paper).toContainText(text);
        expect(await paper.locator('button, aside, nav').count()).toBe(0);
        const layout = await paper.evaluate(element => ({ width: element.getBoundingClientRect().width,
          overflow: element.scrollWidth > element.clientWidth + 1,
          visible: [...document.body.children].filter(child => getComputedStyle(child).display !== 'none').map(child => child.id),
          rule: document.querySelector('style[data-cafe-receipt-page]').textContent }));
        expect(layout.width).toBeCloseTo(72 * 96 / 25.4, 0);
        expect(layout.overflow).toBe(false); expect(layout.visible).toEqual(['cafe-receipt-print-root']);
        expect(layout.rule).toMatch(/size: 80mm \d+mm/);
        if (index === 0) await page.screenshot({ path: path.join(artifacts, 'receipt-print.png'), fullPage: true });
        await page.emulateMedia({ media: 'screen' });
        expect(snapshot()).toBe(beforeReplay);
        await page.getByRole('button', { name: 'Next customer', exact: true }).click();
        await expect(page.getByText('Select menu items to start.', { exact: true })).toBeVisible();
        await expect(page.getByLabel('Search menu', { exact: true })).toHaveValue('');
      }
      expect(new Set(invoices).size).toBe(4);
      const financialBefore = snapshot();
      expect(rows(financialBefore, 'invoices')).toHaveLength(4);
      expect(rows(financialBefore, 'invoice_payments')).toHaveLength(4);
      expect(rows(financialBefore, 'inventory')[0].quantity_on_hand).toBe(93);
      await page.getByRole('button', { name: 'Receipt history', exact: true }).click();
      await page.getByRole('button', { name: `View / reprint ${invoices[0]}`, exact: true }).click();
      for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Reprint receipt', exact: true }).click();
      expect(snapshot()).toBe(financialBefore);
      await logout(); await login(true);
      await expect(metric('Order count')).toHaveText('4');
      for (const [label, amount] of [['Billed sales', 700], ['Collections', 700], ['Cash', 300], ['UPI', 100], ['Card', 300], ['Outstanding', 0], ['Average bill', 175]]) {
        await expect(metric(label)).toContainText(`${amount}.00`);
      }
      await expect(page.getByText('No open orders.', { exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Top-selling items', exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(artifacts, 'owner-today.png'), fullPage: true });
      await page.getByRole('button', { name: 'Inventory', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Inventory and stock ledger', exact: true })).toBeVisible();
      await expect(page.locator('.inventory-table tbody tr').filter({ hasText: 'Audit Sandwich' }).locator('td').nth(4)).toHaveText('93');
      await page.getByRole('button', { name: 'Reports', exact: true }).click();
      await expect(page.getByRole('combobox', { name: /^Period/ })).toHaveValue('Today');
      await page.getByRole('combobox', { name: /^Period/ }).selectOption('This Month');
      await expect(page.getByLabel('From', { exact: true })).toHaveValue(`${today().slice(0, 7)}-01`);
      await expect(page.getByRole('button', { name: 'Download Cafe CSV', exact: true })).toBeEnabled();
      await expect(metric('Net billed revenue')).toContainText('700.00');
      await page.getByRole('combobox', { name: /^Period/ }).selectOption('Custom Range');
      await page.getByLabel('From', { exact: true }).fill(today());
      await page.getByLabel('To', { exact: true }).fill(today());
      await page.getByRole('button', { name: 'Apply dates', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Download Cafe CSV', exact: true })).toBeEnabled();
      await expect(metric('Collections')).toContainText('700.00');
      const downloaded = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Download Cafe CSV', exact: true }).click();
      await (await downloaded).saveAs(path.join(artifacts, 'cafe-report.csv'));
      const csv = readFileSync(path.join(artifacts, 'cafe-report.csv'), 'utf8');
      expect(csv).toContain(',order_count,4');
      expect(csv).toContain(',collections,700.00');
      await page.getByRole('button', { name: 'Daily Closing', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Status: open', exact: true })).toBeVisible();
      await expect(metric('Expected cash')).toHaveText('400.00');
      await expect(metric('Non-cash totals')).toHaveText('400.00');
      await page.getByLabel('Counted cash', { exact: true }).fill('400');
      await page.getByRole('button', { name: 'Submit count', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Status: submitted', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Close day', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Status: closed', exact: true })).toBeVisible();
      await expect(metric('Variance')).toHaveText('0.00');
      await page.reload();
      await expect(page.getByRole('heading', { name: 'Status: closed', exact: true })).toBeVisible();
      expect(outbound).toEqual(['offline.invalid']);
      console.log('PASS production browser: four sequential Cash/UPI/Card bills; duplicate-click/replay safe; 80mm receipt/reprint read-only; owner totals 700, stock 93, reports/CSV, closing 400/400/zero variance; internet blocked.');
    } else {
      await expect(page.getByRole('heading', { name: 'Status: closed', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Inventory', exact: true }).click();
      await expect(page.locator('.inventory-table tbody tr').filter({ hasText: 'Audit Sandwich' }).locator('td').nth(4)).toHaveText('93');
      await page.getByRole('button', { name: 'Dashboard', exact: true }).click();
      await expect(metric('Collections')).toContainText('700.00');
      await logout(); await login(false);
      await page.getByRole('button', { name: 'Receipt history', exact: true }).click();
      await expect(page.getByRole('button', { name: /View \/ reprint/ })).toHaveCount(4);
      const beforeClosedAttempt = snapshot();
      await page.getByRole('button', { name: 'Café POS', exact: true }).click();
      await page.locator('.cafe-pos-menu button').filter({ hasText: 'Audit Sandwich' }).click();
      await page.getByRole('combobox', { name: /^Payment/ }).selectOption({ label: 'Cash' });
      const refused = page.waitForResponse(response => response.url().endsWith('/api/cafe/billing/pos/checkout') && response.request().method() === 'POST');
      await page.getByRole('button', { name: 'Pay & create invoice', exact: true }).click();
      expect((await refused).status()).toBe(409);
      expect(snapshot()).toBe(beforeClosedAttempt);
      await logout();
      expect(outbound).toEqual([]);
      console.log('PASS application API/static-server restart: persisted invoices, inventory, totals and closed day; fresh owner/cashier login; closed day refuses new billing without business effects.');
    }
    expect(errors).toEqual([]);
  } catch (error) {
    await page.screenshot({ path: path.join(artifacts, 'failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
