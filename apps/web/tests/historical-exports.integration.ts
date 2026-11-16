import assert from "node:assert/strict";
import test from "node:test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { businessDate, shiftDate } from "../src/businessDates";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";

function readRows(csv: string) {
  const [header, ...lines] = csv.trim().split("\r\n");
  const columns = header.split(",");
  return lines.map(line => {
    const cells = [...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)].map(match => match[1].replaceAll('""', '"'));
    assert.equal(cells.length, columns.length);
    return Object.fromEntries(columns.map((column, i) => [column, cells[i]]));
  });
}

test("historical CSV streams full and scoped histories, preserves IST and reconciles financial and stock records", { timeout: 120000 }, async () => {
  const mongo = await MongoMemoryReplSet.create({ instanceOpts: [{ args: ["--nounixsocket"] }], replSet: { count: 1, storageEngine: "wiredTiger" } });
  const password = "Exports-test-only-password!";
  Object.assign(process.env, {
    MONGODB_URI: mongo.getUri(), MONGODB_DB: "kalpvriksh_web_test_history_exports", AUTH_SECRET: "history-export-test-secret-at-least-32-chars",
    BOOTSTRAP_OWNER_EMAIL: "owner@example.test", BOOTSTRAP_OWNER_PASSWORD: password,
    BOOTSTRAP_CAFE_CASHIER_EMAIL: "counter@example.test", BOOTSTRAP_CAFE_CASHIER_PASSWORD: password,
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
    const login = (email: string, recovery_code?: string) => call("auth/login", undefined, undefined, { email, password, recovery_code });
    const ownerLogin = await login("owner@example.test", setup.recoveryCodes[0]);
    assert.equal(ownerLogin.status, 200);
    const { access_token: owner, user } = await ownerLogin.json();
    const cashierLogin = await login("counter@example.test");
    assert.equal(cashierLogin.status, 200);
    assert.equal((await call("exports/history/invoices", (await cashierLogin.json()).access_token)).status, 403);
    await db.collection("users").updateOne({ email: "counter@example.test" }, { $set: { role: "store_manager" } });
    const managerLogin = await login("counter@example.test");
    assert.equal(managerLogin.status, 200);
    const manager = (await managerLogin.json()).access_token;
    await db.collection("branches").insertOne({ id: 33, company_id: 1, name: "Other Café branch", is_active: true });
    await db.collection("companies").insertOne({ id: 44, business_group_id: 44, name: "External venture", is_active: true });
    await db.collection("branches").insertOne({ id: 44, company_id: 44, name: "External branch", is_active: true });

    const date = "2025-02-01";
    const midnight = "2025-01-31T18:30:00.000Z";
    const before = "2025-01-31T18:29:59.999Z";
    const ownerId = user.id;
    const scoped = { company_id: 1, branch_id: 1 };
    const grand = "10.11";
    const sample = { ...scoped, invoice_date: midnight, issued_at: midnight, grand_total: grand, paid_amount: grand,
      balance_due: "0.00", items: [{ product_id: 700, quantity: "1.00", line_total: grand, product_name_snapshot: "Café beans" }], status: "paid", payment_status: "paid", created_by: ownerId, invoice_type: "non_gst" };
    const count = 801;
    await db.collection("invoices").insertMany([
      ...Array.from({ length: count }, (_, i) => ({ ...sample, id: i + 100, invoice_number: `CAFE-${i + 100}` })),
      { ...sample, id: 901, invoice_number: "RIGHT-BEFORE", invoice_date: before },
      { ...sample, id: 902, invoice_number: "OTHER-BRANCH", branch_id: 33 },
      { ...sample, id: 903, invoice_number: "OTHER-VENTURE", company_id: 2, branch_id: 2 },
      { ...sample, id: 904, invoice_number: "OTHER-TENANT", company_id: 44, branch_id: 44 },
      { ...sample, id: 905, invoice_number: "CANCELLED-1", status: "cancelled", cancelled_at: midnight },
    ].map(row => ({ ...row, idempotency_key: `export-test-${row.id}` })));
    await db.collection("financial_reversals").insertOne({ ...scoped, id: 3301, invoice_id: 3300, invoice_number: "HISTORICAL-VOID",
      invoice_date: date, original_invoice_datetime: midnight, original_issued_at: midnight, amount: grand,
      created_at: midnight, reversal_type: "void", refund_status: "partial", actor_id: ownerId,
      compensation_json: { invoice_deleted: true, payment_amount: grand } });
    await db.collection("invoice_payments").insertMany([
      { ...scoped, id: 1, invoice_id: 3300, amount: grand, payment_datetime: midnight, mode_type: "cash", received_by: ownerId },
      { ...scoped, id: 2, invoice_id: 100, amount: "30.00", payment_datetime: midnight, mode_type: "credit", is_credit_marker: true, received_by: ownerId },
      { ...scoped, id: 3, invoice_id: 101, amount: "3.00", payment_datetime: midnight, mode_type: "card", receipt_corrected_at: midnight, receipt_corrected_by: ownerId },
    ]);
    await db.collection("customer_payments").insertOne({ ...scoped, id: 7, amount: "2.05", payment_datetime: midnight, mode_type: "upi", received_by: ownerId, reference_number: " \t=IMPORTXML(secret)" });
    await db.collection("invoice_refunds").insertOne({ ...scoped, id: 1, amount: "2.53", refund_date: date, recorded_at: midnight, invoice_id: 3300, payment_id: 1, reversal_id: 3301, mode_type: "cash", actor_id: ownerId });
    await db.collection("expenses").insertMany([
      { ...scoped, id: 1, expense_date: date, category: "stock_purchase", status: "posted", payment_mode: "cash", vendor_name: "Café supplier", amount: "7.01", source_type: "stock_intake", source_id: 1, created_at: midnight },
      { ...scoped, id: 2, expense_date: date, category: "stock_purchase", status: "posted", payment_mode: "credit", amount: "15.00" },
      { ...scoped, id: 3, expense_date: date, category: "stock_purchase", status: "voided", payment_mode: "cash", amount: "6.00" },
    ]);
    await db.collection("stock_intakes").insertOne({ ...scoped, id: 1, purchase_date: date, status: "posted", expense_id: 1, total_amount: "7.01", payment_mode: "cash", created_at: midnight });
    await db.collection("purchase_orders").insertOne({ ...scoped, id: 1, order_date: date, status: "received", po_number: "PO-1", supplier_id: 9, total_amount: "6.01", created_at: midnight });
    await db.collection("products").insertOne({ company_id: 1, id: 700, sku: "SKU-700", name: "Café beans" });
    await db.collection("inventory").insertOne({ ...scoped, id: 77, product_id: 700, quantity_scaled: 700, reserved_scaled: 21, on_order_scaled: 0 });
    await db.collection("stock_movements").insertOne({ ...scoped, id: 4, created_at: midnight, product_id: 700, movement_type: "stock_intake", quantity_change: "7.00", unit_cost: "1.00", reference_id: 1 });
    await db.collection("business_day_closures").insertOne({ ...scoped, id: 1, business_date: date, status: "closed", opening_cash: "5.00", cash_collections: grand,
      cash_refunds: "2.53", cash_expenses: "7.01", expected_cash: "5.57", counted_cash: "5.00", variance: "-0.57", closed_by: ownerId,
      breakdown: { cash_supplier_payments: "7.01" } });

    const selected = `start_date=${date}&end_date=${date}&company_id=1&branch_id=1`;
    const requestCsv = async (kind: string, filter = selected, token = owner) => {
      const response = await call(`exports/history/${kind}?${filter}`, token);
      assert.equal(response.status, 200);
      assert.equal(response.headers.get("content-type"), "text/csv; charset=utf-8");
      assert.equal(response.headers.get("cache-control"), "private, no-store");
      assert.match(response.headers.get("content-disposition") ?? "", new RegExp(kind + ".*\\.csv"));
      return response;
    };
    const rows = async (kind: string, filter = selected, token = owner) => readRows(await (await requestCsv(kind, filter, token)).text());
    const invoiceBody = (await requestCsv("invoices")).body!.getReader();
    const output: Uint8Array[] = [];
    while (true) {
      const chunk = await invoiceBody.read();
      if (chunk.done) break;
      output.push(chunk.value);
    }
    assert(output.length > 2);
    assert.deepEqual(Array.from(output[0].slice(0, 3)), [0xef, 0xbb, 0xbf]);
    const invoices = readRows(Buffer.concat(output).toString("utf8"));
    assert.equal(invoices.length, count + 2);
    assert(!invoices.some(row => row.invoice_number.startsWith("OTHER-") || row.invoice_number === "RIGHT-BEFORE"));
    assert.equal(invoices.find(row => row.invoice_number === "HISTORICAL-VOID")?.invoice_status, "voided");
    assert.equal(invoices.find(row => row.invoice_number === "HISTORICAL-VOID")?.invoice_date, midnight);
    assert.equal(invoices.find(row => row.invoice_number === "CANCELLED-1")?.invoice_status, "cancelled");
    assert.equal(invoices.find(row => row.invoice_number === "CAFE-100")?.invoice_date, midnight);
    const closed = (await rows("closings"))[0];
    assert.equal(closed.variance, "-0.57");
    assert.equal(closed.cash_supplier_payments, "7.01");
    const receipts = await rows("payments");
    assert.equal(receipts.find(row => row.payment_status === "not_received")?.counted_collection, "0.00");
    assert.equal(receipts.find(row => row.payment_status === "credit")?.counted_collection, "0.00");
    assert.equal(receipts.find(row => row.source === "customer_payments")?.transaction_reference, "' \t=IMPORTXML(secret)");
    assert.equal(receipts.find(row => row.payment_id === "1")?.invoice_number, "HISTORICAL-VOID");
    const reversals = await rows("reversals");
    assert.equal(reversals.find(row => row.event_type === "invoice_reversal")?.actual_refund, "0.00");
    assert.equal(reversals.find(row => row.event_type === "refund")?.actual_refund, "2.53");
    assert.equal(reversals.find(row => row.event_type === "payment_correction")?.actual_refund, "0.00");
    const sales = (await rows("sales"))[0];
    const dashboard = await call(`dashboard/cafe?${selected}`, owner, 1);
    const body = await dashboard.json();
    assert.equal(dashboard.status, 200, JSON.stringify(body));
    const { kpis } = body;
    assert.equal(sales.billed_revenue, kpis.net_billed_revenue);
    assert.equal(sales.gross_collections, "12.16");
    assert.equal(sales.refunds, "2.53");
    assert.equal(sales.net_collections, kpis.collections);
    assert.equal(sales.net_collections, "9.63");
    assert.equal((await rows("employees")).find(r => r.employee_id === String(ownerId))?.net_collections, "9.63");
    assert.deepEqual((await rows("consolidated", `start_date=${date}&end_date=${date}`)).map(r => r.company_id), ["1", "2"]);
    assert.equal((await rows("supplier-payments")).map(r => r.posted_paid_amount).join(","), "7.01,0.00,0.00");
    assert.equal((await rows("expenses")).find(r => r.expense_id === "3")?.posted_amount, "0.00");
    assert.equal((await rows("inventory"))[0].product_name, "Café beans");
    assert.equal((await rows("movements"))[0].business_date_ist, date);
    assert.equal((await rows("stock-feeds"))[0].expense_id, "1");
    assert.equal((await rows("purchases"))[0].po_number, "PO-1");
    const today = businessDate(), yesterday = shiftDate(today, -1), monthStart = today.slice(0, 8) + "01", previousMonthEnd = shiftDate(monthStart, -1);
    for (const [preset, start, end] of [
      ["today", today, today], ["yesterday", yesterday, yesterday], ["this_month", monthStart, today],
      ["last_month", previousMonthEnd.slice(0, 8) + "01", previousMonthEnd],
    ]) {
      const csv = await requestCsv("invoices", "company_id=1&preset=" + preset);
      assert.equal(csv.headers.get("content-disposition"), `attachment; filename="invoices-${start}-${end}.csv"`);
      await csv.text();
    }
    const week = await rows("sales", "company_id=1&branch_id=1&start_date=2025-01-27&end_date=2025-02-09&cadence=weekly");
    assert.deepEqual(week.map(r => [r.period_start_ist, r.period_end_ist, r.invoice_count]), [["2025-01-27", "2025-02-02", String(count + 1)]]);
    const month = await rows("sales", "company_id=1&branch_id=1&start_date=2025-01-01&end_date=2025-02-28&cadence=monthly");
    assert.deepEqual(month.map(r => [r.period_start_ist, r.period_end_ist, r.invoice_count]), [["2025-01-01", "2025-01-31", "1"], ["2025-02-01", "2025-02-28", String(count)]]);
    const empty = await (await requestCsv("invoices", "company_id=1&start_date=2024-02-01&end_date=2024-02-02")).text();
    assert.equal(empty.split("\r\n").length, 2);
    assert.match(empty, /^company_id,venture,branch_id,branch,invoice_id,/);
    assert.equal((await rows("invoices", selected, manager)).length, count + 2);
    for (const route of ["invoices?company_id=2", "invoices?branch_id=33", "consolidated"]) assert.equal((await call(`exports/history/${route}`, manager)).status, 403);
    for (const route of ["invoices?company_id=44", "invoices?branch_id=44", "invoices?company_id=2&branch_id=1"]) assert.equal((await call(`exports/history/${route}`, owner)).status, 403);
  } finally {
    await disconnect();
    await mongo.stop();
  }
});
