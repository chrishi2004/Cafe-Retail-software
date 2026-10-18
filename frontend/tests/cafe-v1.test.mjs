import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}
const routing = await load('../src/portalRouting.ts');
const dates = await load('../src/utils/cafeDates.ts');
const cafe = (role) => ({ server_role: role, company_business_type: 'cafe' });

test('cashier and owner land in their own workflows; restricted deep links redirect', () => {
  for (const role of ['staff', 'order_taker']) {
    assert.equal(routing.defaultPathForUser(cafe(role)), '/cafe/pos');
    for (const path of ['/cafe/dashboard', '/cafe/reports', '/cafe/closing', '/cafe/menu', '/retail/overview']) {
      assert.equal(routing.safePathForUser(cafe(role), path), '/cafe/pos');
    }
    assert.equal(routing.safePathForUser(cafe(role), '/cafe/billing'), '/cafe/billing');
    assert.equal(routing.safePathForUser(cafe(role), '/cafe/receipts'), '/cafe/receipts');
  }
  for (const role of ['analyst', 'kitchen']) {
    assert.equal(routing.safePathForUser(cafe(role), '/cafe/receipts'), routing.defaultPathForUser(cafe(role)));
  }
  assert.equal(routing.defaultPathForUser(cafe('admin')), '/cafe/dashboard');
  assert.equal(routing.defaultPathForUser(cafe('kitchen')), '/cafe/kitchen');
  assert.equal(routing.safePathForUser(cafe('store_manager'), '/cafe/closing'), '/cafe/dashboard');
  assert.equal(routing.defaultPathForUser({ server_role: 'staff', company_business_type: 'retail' }), '/retail/overview');
  assert.equal(routing.defaultPathForUser(cafe('super_admin')), '/super-admin/ventures');
});

test('all report presets handle business midnight, month and year boundaries', () => {
  const RealDate = Date;
  globalThis.Date = class extends RealDate { constructor(...args) { super(...(args.length ? args : ['2027-01-01T00:00:00Z'])); } };
  try {
    assert.equal(dates.cafeToday(), '2027-01-01');
    assert.deepEqual(dates.cafeRange('Today'), { startDate: '2027-01-01', endDate: '2027-01-01' });
    assert.deepEqual(dates.cafeRange('Yesterday'), { startDate: '2026-12-31', endDate: '2026-12-31' });
    assert.deepEqual(dates.cafeRange('7 Days'), { startDate: '2026-12-26', endDate: '2027-01-01' });
    assert.deepEqual(dates.cafeRange('This Month'), { startDate: '2027-01-01', endDate: '2027-01-01' });
    assert.deepEqual(dates.cafeRange('Last Month'), { startDate: '2026-12-01', endDate: '2026-12-31' });
  } finally { globalThis.Date = RealDate; }
  globalThis.Date = class extends RealDate { constructor(...args) { super(...(args.length ? args : ['2026-10-18T20:00:00Z'])); } };
  try { assert.equal(dates.cafeToday(), '2026-10-19'); } finally { globalThis.Date = RealDate; }
});
