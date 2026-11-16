import assert from "node:assert/strict";
import test from "node:test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";
import type { ProfitLossReport } from "../src/server/profit-loss";

test("profit and loss separates GST, cancellations, recorded costs and cash by branch, venture and IST period", { timeout: 120000 }, async () => {
  const mongo = await MongoMemoryReplSet.create({ instanceOpts: [{ args: ["--nounixsocket"] }], replSet: { count: 1, storageEngine: "wiredTiger" } });
  const password = "Reporting-test-only-password!";
  Object.assign(process.env, {
    MONGODB_URI: mongo.getUri(), MONGODB_DB: "kalpvriksh_web_test_profit_loss", AUTH_SECRET: "profit-loss-test-secret-at-least-32-chars",
    BOOTSTRAP_OWNER_EMAIL: "owner@example.test", BOOTSTRAP_OWNER_PASSWORD: password,
    BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@example.test", BOOTSTRAP_CAFE_CASHIER_PASSWORD: password,
    BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test", BOOTSTRAP_RETAIL_CASHIER_PASSWORD: password,
  });
  try {
    const setup = await bootstrap();
    const { db } = await database();
    const call = (route: string, token?: string, company?: number, body?: object) => handle(new Request(`http://localhost/api/${route}`, {
      method: body ? "POST" : "GET",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(company ? { "X-Venture-Id": String(company) } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    }), route.split("?")[0].split("/"));
    const ownerLogin = await call("auth/login", undefined, undefined, { email: "owner@example.test", password, recovery_code: setup.recoveryCodes[0] });
    const staffLogin = await call("auth/login", undefined, undefined, { email: "retail@example.test", password });
    assert.equal(ownerLogin.status, 200);
    assert.equal(staffLogin.status, 200);
    const owner = (await ownerLogin.json()).access_token;
    const staff = (await staffLogin.json()).access_token;

    const path = "financial/profit-loss";
    for (const suffix of ["", "/options", "?format=csv"]) assert.equal((await call(path + suffix, staff)).status, 403);
    assert.equal((await call(path, owner, undefined, {})).status, 405);

    await db.collection("branches").insertMany([
      { id: 3, company_id: 2, name: "Other Retail branch", is_active: true },
      { id: 99, company_id: 99, name: "External branch", is_active: true },
    ]);
    await db.collection("companies").insertOne({ id: 99, business_group_id: 999, name: "External venture", is_active: true });
    for (const filter of ["company_id=99", "branch_id=99", "company_id=1&branch_id=2"]) {
      assert.equal((await call(`${path}?${filter}`, owner)).status, 403);
      assert.equal((await call(`${path}?${filter}&format=csv`, owner)).status, 403);
    }
    const optionsResponse = await call(path + "/options", owner);
    assert.equal(optionsResponse.status, 200);
    const options = await optionsResponse.json();
    assert.deepEqual(options.companies.map((row: { id: number }) => row.id), [1, 2]);
    assert.deepEqual(options.branches.map((row: { id: number }) => row.id).sort(), [1, 2, 3]);

    const date = "2025-04-01", midnight = "2025-03-31T18:30:00.000Z", beforeMidnight = "2025-03-31T18:29:59.999Z";
    const retail = { company_id: 2, branch_id: 2 }, cafe = { company_id: 1, branch_id: 1 };
    const base = { ...retail, invoice_date: midnight, issued_at: midnight, status: "paid", invoice_type: "non_gst", balance_due: "0.00" };
    const line = (value: string, cost: string) => ({ taxable_value: value, recorded_cogs: cost, line_total: value });
    await db.collection("invoices").insertMany([
      { ...base, id: 1, grand_total: "118.00", invoice_type: "gst", taxable_total: "100.00", cgst_total: "9.00", sgst_total: "9.00", igst_total: "0.00", cess_total: "0.00", items: [line("100.00", "60.00")] },
      { ...base, id: 2, grand_total: "50.00", status: "credit", balance_due: "50.00", items: [{ taxable_value: "50.00", gross_profit: "30.00", line_total: "50.00" }] },
      { ...base, id: 3, grand_total: "31.00", status: "cancelled", items: [line("31.00", "10.00")] },
      { ...base, id: 4, grand_total: "600.00", status: "cancelled" },
      { ...base, id: 5, grand_total: "25.00", invoice_date: beforeMidnight, items: [line("25.00", "30.00")] },
      { ...base, ...cafe, id: 6, grand_total: "69.00", items: [line("69.00", "20.00")] },
      { ...base, id: 7, branch_id: 3, grand_total: "35.00", items: [{ taxable_value: "35.00", gross_profit: "35.00", line_total: "35.00" }] },
      { ...base, id: 8, company_id: 99, branch_id: 99, grand_total: "999.00", items: [line("999.00", "1.00")] },
      { ...base, id: 9, branch_id: 3, invoice_date: "2025-04-02T12:00:00.000Z", invoice_type: "gst", grand_total: "10.00", items: [line("10.00", "2.00")] },
    ].map(row => ({ ...row, invoice_number: (row.id === 4 ? "DRAFT-" : "TEST-") + row.id, idempotency_key: "pl-fixture-" + row.id })));
    await db.collection("financial_reversals").insertMany([
      { ...retail, id: 1, invoice_id: 3, amount: "31.00", invoice_date: date, reversal_type: "void", compensation_json: { invoice_deleted: true } },
      { ...retail, id: 2, invoice_id: 88, amount: "39.00", invoice_date: date, reversal_type: "void", refund_status: "partial", compensation_json: { invoice_deleted: true } },
      { ...retail, id: 3, invoice_id: 88, amount: "39.00", invoice_date: date, reversal_type: "void", refund_status: "partial", compensation_json: { invoice_deleted: true } },
    ]);
    const receipt = (id: number, mode_type: string, amount: string, invoice_id: number) => ({ ...retail, id, mode_type, amount, invoice_id, payment_datetime: midnight });
    await db.collection("invoice_payments").insertMany([
      receipt(1, "cash", "118.00", 1),
      { ...receipt(2, "cash", "39.00", 88), voided_at: midnight },
      receipt(3, "card", "31.00", 3),
      { ...receipt(4, "credit", "50.00", 2), is_credit_marker: true },
      { ...receipt(5, "card", "99.00", 88), receipt_corrected_at: midnight },
    ]);
    await db.collection("customer_payments").insertOne({ ...retail, id: 1, mode_type: "upi", amount: "5.00", payment_datetime: midnight });
    await db.collection("invoice_refunds").insertMany([
      { ...retail, id: 1, invoice_id: 88, mode_type: "cash", amount: "9.00", refund_date: date },
      { ...retail, id: 2, invoice_id: 3, mode_type: "upi", amount: "3.00", refund_date: date },
      { ...retail, id: 3, invoice_id: 88, mode_type: "cash", amount: "4.00", refund_date: "2025-04-02" },
    ]);
    const expense = (id: number, category: string, payment_mode: string, amount: string) => ({ ...retail, id, category, expense_date: date, status: "posted", payment_mode, amount });
    await db.collection("expenses").insertMany([
      expense(1, "rent", "cash", "10.00"),
      expense(2, "utilities", "credit", "7.00"),
      expense(3, "stock_purchase", "cash", "100.00"),
      { ...expense(4, "maintenance", "cash", "40.00"), status: "voided" },
      { ...expense(5, "stock_purchase", "cash", "65.00"), ...cafe, source_type: "stock_intake", source_id: 1 },
      { ...expense(6, "stock_purchase", "credit", "10.00"), ...cafe },
      { ...expense(7, "utilities", "card", "12.00"), ...cafe },
      { ...expense(8, "miscellaneous", "cash", "2.00"), ...cafe, source_type: "supplier_payment" },
    ]);
    await db.collection("stock_intakes").insertOne({ ...cafe, id: 1, status: "posted", purchase_date: date, total_amount: "65.00", expense_id: 5 });
    await db.collection("stock_movements").insertMany([
      { ...retail, id: 1, created_at: midnight, reference_type: "purchase_order", movement_type: "purchase_received", line_total: "25.00", unit_cost: "5.00" },
      { ...retail, id: 2, created_at: midnight, reference_type: "purchase_order", movement_type: "purchase_received", quantity_change: "1.00" },
    ]);
    await db.collection("purchase_orders").insertOne({ ...retail, id: 1, order_date: date, status: "ordered", total_amount: "999.00" });
    await db.collection("customers").insertOne({ ...retail, id: 1, outstanding_scaled: 4500, password_hash: "do-not-expose" });
    await db.collection("business_day_closures").insertMany([
      { ...retail, id: 1, status: "open", business_date: date, opening_cash: "20.00" },
      { ...cafe, id: 2, status: "open", business_date: date, opening_cash: "100.00" },
    ]);

    const report = async (filters: string, dateFrom = date, dateTo = date) => {
      const resp = await call(`${path}?start_date=${dateFrom}&end_date=${dateTo}&${filters}`, owner);
      const data = await resp.json();
      assert.equal(resp.status, 200, JSON.stringify(data));
      assert.equal(resp.headers.get("cache-control"), "private, no-store");
      return data as ProfitLossReport;
    };
    const r = await report("company_id=2&branch_id=2");
    assert.deepEqual(r.previous_period, { start: "2025-03-31", end: "2025-03-31" });
    assert.equal(r.previous.net_recognized_sales, "25.00");
    assert.equal(r.previous.gross_margin_percent, "-20.00");
    assert.equal(r.previous.operating_result, "-5.00");
    assert.deepEqual({
      billed: r.current.gross_billed_sales, adjustments: r.current.cancelled_sales_adjustments, netBilled: r.current.net_billed_sales,
      recognized: r.current.net_recognized_sales, tax: r.current.recorded_sales_tax, cogs: r.current.recorded_cogs, profit: r.current.gross_profit,
      margin: r.current.gross_margin_percent, opEx: r.current.operating_expenses, purchases: r.current.stock_purchases, result: r.current.operating_result,
    }, { billed: "238.00", adjustments: "-70.00", netBilled: "168.00", recognized: "150.00", tax: "18.00", cogs: "80.00",
      profit: "70.00", margin: "46.67", opEx: "17.00", purchases: "125.00", result: "53.00" });
    assert.equal(r.current.quality.inferred_cost_lines, 1);
    assert.equal(r.current.quality.recorded_cost_lines, 1);
    assert.equal(r.current.quality.reversed_invoices, 2);
    assert.equal(r.current.quality.unpriced_stock_receipts, 1);
    assert.equal(r.current.quality.excluded_drafts, 1);
    assert.equal(r.current.gross_collections, "193.00");
    assert.equal(r.current.cash_collections, "157.00");
    assert.equal(r.current.upi_collections, "5.00");
    assert.equal(r.current.card_collections, "31.00");
    assert.equal(r.current.actual_refunds, "12.00");
    assert.equal(r.current.net_collections, "181.00");
    assert.equal(r.current.outstanding_invoice_credit, "50.00");
    assert.equal(r.current_customer_ledger_credit, null);
    assert.equal(r.supplier_payables, null);
    assert.deepEqual(r.expenses_by_category, [{ category: "rent", amount: "10.00" }, { category: "utilities", amount: "7.00" }]);
    assert.deepEqual(r.trend, [{ period_ist: date, net_recognized_sales: "150.00", operating_expenses: "17.00", stock_purchases: "125.00" }]);

    const closing = await call(`governance/closings?preview=true&business_date=${date}&branch_id=2`, owner, 2);
    assert.equal(closing.status, 200);
    const close = await closing.json();
    assert.equal(close.cash_collections, r.current.cash_collections);
    assert.equal(close.cash_refunds, r.current.actual_cash_refunds);
    assert.equal(close.breakdown.cash_operating_expenses, r.current.cash_operating_expenses);
    assert.equal(close.breakdown.cash_supplier_payments, r.current.cash_supplier_outflows);
    assert.equal(close.non_cash_total, "36.00");
    assert.equal(close.expected_cash, "58.00");
    const later = await report("branch_id=2", "2025-04-02", "2025-04-02");
    assert.equal(later.current.net_recognized_sales, "0.00");
    assert.equal(later.current.net_collections, "-4.00");
    assert.equal(later.previous.net_recognized_sales, r.current.net_recognized_sales);

    const cafeOnly = await report("company_id=1");
    assert.equal(cafeOnly.current.recorded_cogs, "20.00");
    assert.equal(cafeOnly.current.quality.status, "cost_data_incomplete");
    assert.equal(cafeOnly.current.quality.cafe_lines_without_recipe_cost, 1);
    assert.equal(cafeOnly.current.gross_profit, null);
    assert.equal(cafeOnly.current.operating_result, null);
    assert.equal(cafeOnly.current.stock_purchases, "75.00");
    assert.equal(cafeOnly.current.operating_expenses, "12.00");
    assert.equal(cafeOnly.current.cash_supplier_outflows, "67.00");
    const cafeClosing = await call(`governance/closings?preview=true&business_date=${date}&branch_id=1`, owner, 1);
    assert.equal(cafeClosing.status, 200);
    assert.equal((await cafeClosing.json()).breakdown.cash_supplier_payments, cafeOnly.current.cash_supplier_outflows);
    const combined = await report("");
    assert.equal(combined.current.net_recognized_sales, "254.00");
    assert.equal(combined.current.operating_result, null);
    assert.equal(combined.current_customer_ledger_credit, "45.00");
    assert.equal(combined.by_venture[1].current.quality.missing_cost_lines, 1);
    const unknownGST = await report("branch_id=3", "2025-04-02", "2025-04-02");
    assert.equal(unknownGST.current.quality.status, "billing_data_incomplete");
    assert.equal(unknownGST.current.net_recognized_sales, null);
    assert.equal(unknownGST.trend[0].net_recognized_sales, null);
    const wide = await report("branch_id=2", "2025-01-01", "2025-06-30");
    assert.equal(wide.trend_interval, "month");
    assert.equal(wide.trend.length, 6);
    assert.equal(wide.trend[3].net_recognized_sales, "150.00");

    const csv = await call(`${path}?format=csv&start_date=${date}&end_date=${date}&branch_id=2`, owner);
    assert.match(csv.headers.get("content-disposition") ?? "", /^attachment; filename="profit-loss-2025-04-01/);
    const exported = await csv.text();
    assert(exported.includes("net_recognized_sales") && exported.includes('"150.00"') && exported.includes('"53.00"'));
    assert(exported.includes('"previous_period"') && exported.includes('"expense_category"') && exported.includes('"trend"'));
    for (const privateValue of ["do-not-expose", "External venture"]) assert(!exported.includes(privateValue));
    assert.equal(await db.collection("invoices").countDocuments(), 9);
    assert.equal(await db.collection("invoice_refunds").countDocuments(), 3);
  } finally {
    await disconnect();
    await mongo.stop();
  }
});
