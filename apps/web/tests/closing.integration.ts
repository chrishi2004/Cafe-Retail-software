import assert from "node:assert/strict";
import test from "node:test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";
import { businessDate } from "../src/server/money";
import { hashPassword, totp } from "../src/server/security";

test("Daily Closing separates settled payments, refunds and expenses, and preserves scoped IST snapshots", { timeout: 120000 }, async () => {
  const mongo = await MongoMemoryReplSet.create({
    instanceOpts: [{ args: ["--nounixsocket"] }],
    replSet: { count: 1, storageEngine: "wiredTiger" },
  });
  const ownerPassword = "Closing-owner-password-123!";
  const staffPassword = "Closing-staff-password-123!";
  Object.assign(process.env, {
    MONGODB_URI: mongo.getUri(), MONGODB_DB: "kalpvriksh_web_test_closing",
    AUTH_SECRET: "closing-test-only-auth-secret-credentials",
    BOOTSTRAP_OWNER_EMAIL: "owner@example.test", BOOTSTRAP_OWNER_PASSWORD: ownerPassword,
    BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@example.test", BOOTSTRAP_CAFE_CASHIER_PASSWORD: staffPassword,
    BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test", BOOTSTRAP_RETAIL_CASHIER_PASSWORD: staffPassword,
  });
  try {
    const setup = await bootstrap();
    const { db } = await database();
    await db.collection("branches").insertOne({ id: 83, name: "Other Retail branch", company_id: 2, is_active: true });
    await db.collection("users").insertOne({
      id: 90, business_group_id: 1, company_id: 2, branch_id: 2, name: "Retail Manager",
      email: "manager@example.test", role: "store_manager", is_active: true,
      password_hash: await hashPassword(staffPassword), token_version: 1, mfa_enabled: false,
    });
    let owner = "";
    const request = (path: string, method = "GET", body?: object, venture = 2, token = owner, key?: string) =>
      handle(new Request(`http://localhost/api/${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, "X-Venture-Id": String(venture), ...(key ? { "Idempotency-Key": key } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      }), path.split("?")[0].split("/"));
    const call = async (...args: Parameters<typeof request>) => {
      const result = await request(...args);
      return { status: result.status, body: await result.json() };
    };
    const ok = async (...args: Parameters<typeof request>) => {
      const result = await call(...args);
      assert.equal(result.status, 200, `${args[1] ?? "GET"} ${args[0]}: ${JSON.stringify(result.body)}`);
      return result.body;
    };
    owner = (await ok("auth/login", "POST", {
      email: "owner@example.test", password: ownerPassword, recovery_code: setup.recoveryCodes[0],
    })).access_token;
    const cashier = (await ok("auth/login", "POST", { email: "retail@example.test", password: staffPassword })).access_token;
    const manager = (await ok("auth/login", "POST", { email: "manager@example.test", password: staffPassword })).access_token;
    const day = businessDate();
    const base = "governance/closings";
    const viewPath = (branchId: number, date = day) => `${base}?branch_id=${branchId}&business_date=${date}&preview=true`;
    const open = { branch_id: 2, business_date: day, opening_cash: "50" };
    const copies = await Promise.all([ok(base, "POST", open, 2, manager), ok(base, "POST", open, 2, manager)]);
    assert.equal(copies[0].id, copies[1].id);
    const closeId = copies[0].id;
    assert.equal((await call(base, "POST", { ...open, opening_cash: "41" })).status, 409);
    assert.equal((await call(viewPath(2), "GET", undefined, 2, cashier)).status, 403);
    assert.equal((await call(viewPath(83), "GET", undefined, 2, manager)).status, 403);
    assert.equal((await call(viewPath(1), "GET", undefined, 2)).status, 404);
    assert.equal((await call(viewPath(2), "GET", undefined, 1)).status, 404);

    await db.collection("products").insertMany([
      { id: 91, company_id: 2, name: "Till fixture", sku: "TILL", selling_price: "100.00", unit_cost: "25.00", is_active: true },
      { id: 92, company_id: 1, name: "Café stock", sku: "CAFE-STOCK", selling_price: "20.00", unit_cost: "2.00", is_active: true },
    ]);
    await db.collection("inventory").insertOne({ id: 91, company_id: 2, branch_id: 2, product_id: 91, quantity_scaled: 2000 });
    await db.collection("payment_modes").insertOne({ id: 91, company_id: 2, name: "Bank", mode_type: "bank_transfer", is_active: true });
    const customer = await ok("customers", "POST", { branch_id: 2, name: "Credit customer", credit_limit: "1000.00", opening_balance: "250.00" });
    const sale = (payments: Array<{ payment_mode_id: number; amount: string }>, key: string) =>
      ok("pos/checkout", "POST", {
        branch_id: 2, customer_id: customer.id, invoice_type: "non_gst",
        items: [{ product_id: 91, quantity: "1" }], payments,
      }, 2, cashier, key);
    const whole = (payment_mode_id: number) => [{ payment_mode_id, amount: "100" }];
    const cash = await sale(whole(4), "closing-cash");
    const upi = await sale(whole(5), "closing-upi");
    await sale(whole(6), "closing-card");
    await sale(whole(91), "closing-bank");
    const partial = await sale([{ payment_mode_id: 4, amount: "20" }, { payment_mode_id: 5, amount: "10" }], "closing-partial");
    const unpaid = await sale([], "closing-unpaid");
    assert.equal(unpaid.balance_due, "100.00");
    assert.equal((await ok(`invoices/${partial.id}/payments`, "POST", { payment_mode_id: 4, amount: "25" }, 2, cashier, "closing-invoice-repay")).balance_due, "45.00");
    const paymentPath = `customers/${customer.id}/payments`;
    const payment = { branch_id: 2, amount: "15", payment_mode_id: 4 };
    const receipts = await Promise.all([
      ok(paymentPath, "POST", payment, 2, cashier, "cash-repayment"),
      ok(paymentPath, "POST", payment, 2, cashier, "cash-repayment"),
    ]);
    assert.equal(receipts[0].id, receipts[1].id);
    assert.equal(await db.collection("customer_payments").countDocuments({ company_id: 2, branch_id: 2 }), 1);

    const expense = (category: string, amount: string, payment_mode: string, key: string) =>
      ok("expenses", "POST", { branch_id: 2, expense_date: day, description: category, category, amount, payment_mode }, 2, manager, key);
    const same = await Promise.all([
      expense("maintenance", "18", "cash", "cash-expense"),
      expense("maintenance", "18", "cash", "cash-expense"),
    ]);
    assert.equal(same[0].id, same[1].id);
    await expense("stock_purchase", "7", "cash", "supplier-cash");
    await expense("utilities", "4", "upi", "electronic-expense");
    await expense("stock_purchase", "60", "credit", "credit-supplier");

    for (const invoice of [cash, upi])
      await ok(`governance/voids/invoices/${invoice.id}`, "POST", { confirmed: true, delete_permanently: true }, 2, owner, `void-closing-${invoice.id}`);
    const pending = await ok(viewPath(2), "GET", undefined, 2, manager);
    assert.equal(pending.cash_collections, "160.00");
    assert.equal(pending.cash_refunds, "0.00");
    assert.equal(pending.expected_cash, "185.00");
    const cases = (await ok("governance/refunds")).items;
    const recordRefund = (invoiceNumber: string, amount: string, reference?: string) => {
      const row = cases.find((p: { invoice_number: string }) => p.invoice_number === invoiceNumber);
      return ok(`governance/refunds/${row.id}/payments/${row.payments[0].id}`, "POST",
        { action: "refund", confirmed: true, refund_date: day, amount, reference_number: reference }, 2, owner, `refund-${row.id}-${amount}`);
    };
    await recordRefund(cash.invoice_number, "30");
    await recordRefund(upi.invoice_number, "20", "upi-reversal-test");
    const preview = await ok(viewPath(2));
    assert.deepEqual(preview.breakdown, {
      sales: { cash: "120.00", upi: "110.00", card: "100.00", other_electronic: "100.00", other_non_cash: "0.00" },
      repayments: { cash: "40.00", upi: "0.00", card: "0.00", other_electronic: "0.00", other_non_cash: "0.00" },
      refunds: { cash: "30.00", upi: "20.00", card: "0.00", other_electronic: "0.00", other_non_cash: "0.00" },
      cash_operating_expenses: "18.00", cash_supplier_payments: "7.00",
    });
    assert.equal(preview.non_cash_total, "310.00");
    assert.equal(preview.non_cash_expenses, "4.00");
    assert.equal(preview.expected_cash, "155.00");

    await expense("cleaning", "1", "cash", "stale-preview-expense");
    const submit = `${base}/${closeId}/submit`;
    const stale = await call(submit, "POST", { counted_cash: "150", preview_token: preview.preview_token }, 2, manager);
    assert.equal(stale.body.error.code, "closing_preview_changed");
    const fresh = await ok(viewPath(2));
    const [counted, racing] = await Promise.all([
      call(submit, "POST", { counted_cash: "150", preview_token: fresh.preview_token }, 2, manager),
      call(paymentPath, "POST", { ...payment, amount: "2" }, 2, cashier, "racing-repayment"),
    ]);
    assert.deepEqual([counted.status, racing.status].sort(), [200, 409]);
    if (counted.status === 409) assert.equal(counted.body.error.code, "closing_preview_changed");
    else assert.equal(racing.body.error.code, "day_closed");
    const latest = await ok(viewPath(2));
    const final = await ok(submit, "POST", { counted_cash: "150", preview_token: latest.preview_token }, 2, manager);
    const expected = racing.status === 200 ? "156.00" : "154.00";
    assert.equal(final.expected_cash, expected);
    assert.equal(final.variance, racing.status === 200 ? "-6.00" : "-4.00");
    assert.equal((await ok(`${base}/${closeId}/close`, "POST", {}, 2, manager)).status, "closed");
    await ok(`${base}/${closeId}/close`, "POST", {}, 2, manager);
    assert.equal((await call(paymentPath, "POST", { ...payment, amount: "4" }, 2, cashier, "blocked-repayment")).body.error.code, "day_closed");
    assert.equal((await call(`invoices/${partial.id}/payments`, "POST", { payment_mode_id: 4, amount: "2" }, 2, cashier, "blocked-invoice-payment")).body.error.code, "day_closed");
    assert.equal((await call("expenses", "POST", { branch_id: 2, expense_date: day, category: "wages", amount: "4", payment_mode: "cash" })).body.error.code, "day_closed");
    const cashCase = cases.find((r: { invoice_number: string }) => r.invoice_number === cash.invoice_number);
    assert.equal((await call(`governance/refunds/${cashCase.id}/payments/${cashCase.payments[0].id}`, "POST",
      { action: "refund", confirmed: true, refund_date: day, amount: "5" }, 2, owner, "blocked-refund")).body.error.code, "day_closed");

    const exported = await request(`${viewPath(2)}&format=csv`);
    assert.equal(exported.status, 200);
    assert.match(exported.headers.get("content-type") ?? "", /^text\/csv/);
    const csv = await exported.text();
    assert.match(csv, /"cash_supplier_payments"/);
    assert(csv.includes(`"${expected}"`) && csv.includes('"Retail Manager"'));
    assert.equal((await request(`${viewPath(83)}&format=csv`, "GET", undefined, 2, manager)).status, 403);
    assert.equal((await db.collection("audit_events").countDocuments({ action: "close", entity_type: "business_day_closure", entity_id: closeId })), 1);

    // A linked cash purchase is counted once, while credit and stock-only entries are excluded.
    const intake = (amount: string, payment_mode: string, record_expense: boolean, key: string) =>
      ok("cafe/stock-intakes", "POST", { branch_id: 1, purchase_date: day, vendor_name: "Fixture supplier",
        payment_mode, record_expense, items: [{ product_id: 92, quantity: "1", unit_cost: amount }] }, 1, owner, key);
    await intake("12", "cash", true, "cafe-outflow-cash");
    await intake("25", "credit", true, "cafe-stock-credit");
    await intake("100", "cash", false, "cafe-stock-only");
    await ok(base, "POST", { branch_id: 1, business_date: day, opening_cash: "20" }, 1);
    const cafe = await ok(viewPath(1), "GET", undefined, 1);
    assert.equal(cafe.breakdown.cash_supplier_payments, "12.00");
    assert.equal(cafe.non_cash_expenses, "0.00");
    assert.equal(cafe.expected_cash, "8.00");

    // The two UTC timestamps are adjacent but refer to different IST business days.
    const historical = "2024-02-01";
    await db.collection("business_day_closures").insertMany([
      { id: 91, company_id: 2, branch_id: 83, business_date: historical, opening_cash: "0.00", status: "open" },
      { id: 92, company_id: 2, branch_id: 83, business_date: "2024-01-31", opening_cash: "8.00", expected_cash: "9.00",
        counted_cash: "9.00", variance: "0.00", status: "closed", closed_by: 90, cash_collections: "1.00" },
    ]);
    await db.collection("invoice_payments").insertMany([
      { id: 910, company_id: 2, branch_id: 83, mode_type: "cash", amount: "11.00", payment_datetime: "2024-01-31T18:29:59.999Z" },
      { id: 911, company_id: 2, branch_id: 83, mode_type: "cash", amount: "13.00", payment_datetime: "2024-01-31T18:30:00.000Z" },
      { id: 912, company_id: 2, branch_id: 83, mode_type: "cash", amount: "17.00", payment_datetime: "2024-02-01T18:30:00.000Z" },
    ]);
    assert.equal((await ok(viewPath(83, historical))).expected_cash, "13.00");
    const historic = await ok(viewPath(83, "2024-01-31"));
    assert.equal(historic.expected_cash, "9.00");
    assert.equal(historic.breakdown, undefined);
    assert.equal(historic.closed_by_name, "Retail Manager");

    const reopen = `${base}/${closeId}/reopen`;
    assert.equal((await call(reopen, "POST", { reason: "Review drawer line" }, 2, manager)).status, 403);
    assert.equal((await call(reopen, "POST", { reason: "Review drawer line" })).body.error.code, "step_up_required");
    await ok("auth/step-up", "POST", { password: ownerPassword, totp_code: totp(setup.totpSecret) });
    assert.equal((await call(reopen, "POST", { reason: "" })).status, 422);
    assert.equal((await ok(reopen, "POST", { reason: "Review drawer line" })).status, "reopened");
    const audit = await db.collection("audit_events").findOne({ action: "reopen", entity_id: closeId });
    assert.equal(audit?.details.prior_snapshot.expected_cash, expected);
    assert.equal(audit?.details.prior_snapshot.status, "closed");
    assert.equal(audit?.branch_id, 2);
  } finally {
    await disconnect();
    await mongo.stop();
  }
});
