import test from "node:test";
import assert from "node:assert/strict";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { database, disconnect } from "../src/server/db";
import { bootstrap } from "../src/server/bootstrap";
import { handle } from "../src/server/handler";
import { totp } from "../src/server/security";

test(
  "native Mongo transactions: auth, scoped sales, concurrent duplicate/stock protection, receipt read-only, closing",
  { timeout: 180000 },
  async () => {
    const server = await MongoMemoryReplSet.create({
      instanceOpts: [{ args: ["--nounixsocket"] }],
      replSet: { count: 1, storageEngine: "wiredTiger" },
    });
    process.env.MONGODB_URI = server.getUri();
    process.env.MONGODB_DB = "kalpvriksh_web_test_integration";
    process.env.AUTH_SECRET = "integration-only-auth-secret-with-32-characters";
    Object.assign(process.env, {
      BOOTSTRAP_OWNER_EMAIL: "owner@example.test",
      BOOTSTRAP_OWNER_PASSWORD: "Owner-password-123!",
      BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@example.test",
      BOOTSTRAP_CAFE_CASHIER_PASSWORD: "Cafe-password-123!",
      BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test",
      BOOTSTRAP_RETAIL_CASHIER_PASSWORD: "Retail-password-123!",
    });
    try {
      const enrolled = await bootstrap();
      const { db } = await database();
      await assert.rejects(bootstrap, /NEW database/);
      const call = async (
        path: string,
        method = "GET",
        body?: unknown,
        token?: string,
        key?: string,
        venture?: number,
      ) => {
        const response = await handle(
          new Request(`http://localhost/api/${path}`, {
            method,
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
              ...(key ? { "Idempotency-Key": key } : {}),
              ...(venture ? { "X-Venture-Id": String(venture) } : {}),
            },
            body: body === undefined ? undefined : JSON.stringify(body),
          }),
          path.split("?")[0].split("/"),
        );
        return { status: response.status, body: await response.json() };
      };
      const owner = await call("auth/login", "POST", {
        email: "owner@example.test",
        password: "Owner-password-123!",
        totp_code: totp(enrolled.totpSecret),
      });
      assert.equal(owner.status, 200);
      const ot = owner.body.access_token;
      const cashier = await call("auth/login", "POST", {
        email: "cafe@example.test",
        password: "Cafe-password-123!",
      });
      assert.equal(cashier.status, 200);
      const ct = cashier.body.access_token;
      const retail = await call("auth/login", "POST", {
        email: "retail@example.test",
        password: "Retail-password-123!",
      });
      assert.equal(retail.status, 200);
      const rt = retail.body.access_token;
      assert.equal((await call("ventures", "GET", undefined, ct)).status, 403);
      assert.equal(
        (await call("branches", "GET", undefined, ct, undefined, 2)).status,
        403,
      );
      assert.equal((await call("public/invoices", "POST", {})).status, 404);
      const category = await call(
        "categories",
        "POST",
        { name: "Stock" },
        ot,
        undefined,
        1,
      );
      assert.equal(category.status, 200);
      const supplier = await call(
        "suppliers",
        "POST",
        { name: "Supplier" },
        ot,
        undefined,
        1,
      );
      assert.equal(supplier.status, 200);
      const product = await call(
        "products",
        "POST",
        {
          name: "Sandwich",
          sku: "SANDWICH",
          category_id: category.body.id,
          supplier_id: supplier.body.id,
          selling_price: "100.00",
          unit_cost: "40.00",
        },
        ot,
        undefined,
        1,
      );
      assert.equal(product.status, 200);
      const menuCategory = await call(
        "cafe/menu/categories",
        "POST",
        { name: "Menu", branch_id: 1 },
        ot,
        undefined,
        1,
      );
      const item = await call(
        "cafe/menu/items",
        "POST",
        {
          name: "Sandwich",
          category_id: menuCategory.body.id,
          branch_id: 1,
          product_id: product.body.id,
          selling_price: "100.00",
        },
        ot,
        undefined,
        1,
      );
      assert.equal(item.status, 200);
      assert.equal(
        (
          await call(
            "inventory/adjustments",
            "POST",
            {
              branch_id: 1,
              product_id: product.body.id,
              quantity_change: "10",
              reason: "Opening stock",
            },
            ot,
            undefined,
            1,
          )
        ).status,
        200,
      );
      const payload = (mode: number, quantity = 1) => ({
        branch_id: 1,
        items: [{ menu_item_public_id: item.body.public_id, quantity }],
        order_type: "counter",
        payment_mode_id: mode,
      });
      for (const mode of [1, 2, 3])
        assert.equal(
          (
            await call(
              "cafe/billing/pos/checkout",
              "POST",
              payload(mode),
              ct,
              `mode-${mode}-sale`,
            )
          ).status,
          200,
        );
      const duplicates = await Promise.all([
        call(
          "cafe/billing/pos/checkout",
          "POST",
          payload(1),
          ct,
          "duplicate-pay-key",
        ),
        call(
          "cafe/billing/pos/checkout",
          "POST",
          payload(1),
          ct,
          "duplicate-pay-key",
        ),
      ]);
      assert(
        duplicates.every((r) => r.status === 200),
        JSON.stringify(duplicates),
      );
      assert.equal(
        duplicates[0].body.receipt.invoice_id,
        duplicates[1].body.receipt.invoice_id,
      );
      const before = {
        invoices: await db.collection("invoices").countDocuments(),
        payments: await db.collection("invoice_payments").countDocuments(),
        moves: await db.collection("stock_movements").countDocuments(),
        stock: (
          await db
            .collection("inventory")
            .findOne({ product_id: product.body.id })
        )?.quantity_scaled,
      };
      const receiptPath = `cafe/billing/invoices/${duplicates[0].body.receipt.invoice_id}/receipt`;
      assert.equal((await call(receiptPath, "GET", undefined, ct)).status, 200);
      assert.equal((await call(receiptPath, "GET", undefined, rt)).status, 404);
      assert.deepEqual(
        {
          invoices: await db.collection("invoices").countDocuments(),
          payments: await db.collection("invoice_payments").countDocuments(),
          moves: await db.collection("stock_movements").countDocuments(),
          stock: (
            await db
              .collection("inventory")
              .findOne({ product_id: product.body.id })
          )?.quantity_scaled,
        },
        before,
      );
      assert.equal(
        (
          await call(
            "cafe/billing/pos/checkout",
            "POST",
            payload(1, 2),
            ct,
            "duplicate-pay-key",
          )
        ).status,
        409,
      );
      const sales = await Promise.all([
        call(
          "cafe/billing/pos/checkout",
          "POST",
          payload(1, 6),
          ct,
          "last-stock-a",
        ),
        call(
          "cafe/billing/pos/checkout",
          "POST",
          payload(1, 6),
          ct,
          "last-stock-b",
        ),
      ]);
      assert.deepEqual(sales.map((r) => r.status).sort(), [200, 409]);
      assert.equal(
        (
          await db
            .collection("inventory")
            .findOne({ product_id: product.body.id })
        )?.quantity_scaled,
        0,
      );
      const dashboard = await call(
        "dashboard/cafe",
        "GET",
        undefined,
        ot,
        undefined,
        1,
      );
      assert.equal(dashboard.body.kpis.billed_revenue, "1000.00");
      assert.equal(dashboard.body.kpis.collections, "1000.00");
      assert.equal(
        (
          await call(
            "governance/closings",
            "POST",
            {
              branch_id: 1,
              business_date: new Intl.DateTimeFormat("en-CA", {
                timeZone: "Asia/Kolkata",
                year: "numeric",
                month: "2-digit",
                day: "2-digit",
              }).format(new Date()),
              opening_cash: "100",
            },
            ct,
          )
        ).status,
        403,
      );
      const invoiceId = duplicates[0].body.receipt.invoice_id;
      const voidPath = `governance/voids/invoices/${invoiceId}`;
      const deletion = { confirmed: true, delete_permanently: true };
      assert.equal((await call(voidPath, "POST", deletion, ct, "void-cashier")).status, 403);
      assert.equal((await call(voidPath, "POST", deletion, ot, "void-wrong-venture", 2)).status, 404);
      assert.equal((await call(voidPath, "POST", { confirmed: true }, ot, "void-stale-client", 1)).status, 422);
      assert.equal((await call("governance/step-up", "GET", undefined, ot)).body.remaining_ms, 0);
      const voids = await Promise.all([
        call(voidPath, "POST", deletion, ot, "void-test-sale", 1),
        call(voidPath, "POST", deletion, ot, "void-test-sale", 1),
      ]);
      assert.deepEqual(voids.map((r) => r.status), [200, 200]);
      assert.deepEqual(voids[0].body, voids[1].body);
      assert.equal(voids[0].body.refund_status, "pending");
      assert.equal((await call(voidPath, "POST", deletion, ot, "void-already-done", 1)).status, 404);
      assert.equal(await db.collection("invoices").countDocuments({ id: invoiceId }), 0);
      assert.equal(await db.collection("financial_reversals").countDocuments({ invoice_id: invoiceId }), 1);
      assert.equal((await db.collection("inventory").findOne({ product_id: product.body.id }))?.quantity_scaled, 0);
      assert.equal(await db.collection("cafe_orders").countDocuments({ billed_invoice_id: invoiceId }), 0);
      assert.equal((await call(receiptPath, "GET", undefined, ct)).status, 404);
      assert.equal((await call("cafe/billing/pos/checkout", "POST", payload(1), ct, "duplicate-pay-key")).body.error.code, "invoice_deleted");
      const report = async () => (await call("dashboard/cafe", "GET", undefined, ot, undefined, 1)).body.kpis;
      const corrected = await report();
      assert.equal(corrected.net_billed_revenue, "900.00");
      assert.equal(corrected.ordered_value, "900.00");
      assert.equal(corrected.void_value, "100.00");
      assert.equal(corrected.order_count, 4);
      assert.equal(corrected.collections, "1000.00");
      assert.equal(corrected.refunds, "0.00");
      const pending = await call("governance/refunds", "GET", undefined, ot, undefined, 1);
      assert.equal(pending.status, 200);
      const refundCase = pending.body.items[0];
      assert.equal(refundCase.payments[0].amount, "100.00");
      const refundPath = `governance/refunds/${refundCase.id}/payments/${refundCase.payments[0].id}`;
      const refund = { action: "refund", confirmed: true, refund_date: refundCase.payments[0].received_date };
      assert.equal((await call(refundPath, "POST", { ...refund, amount: "40" }, ct, "refund-cashier", 1)).status, 403);
      assert.equal((await call(refundPath, "POST", { ...refund, amount: "40" }, ot, "refund-other-scope", 2)).status, 404);
      assert.equal((await call(refundPath, "POST", { ...refund, amount: "101" }, ot, "refund-too-much", 1)).status, 422);
      const partial = await Promise.all([
        call(refundPath, "POST", { ...refund, amount: "40" }, ot, "partial-refund", 1),
        call(refundPath, "POST", { ...refund, amount: "40" }, ot, "partial-refund", 1),
      ]);
      for (const result of partial) {
        assert.equal(result.status, 200, JSON.stringify(result.body));
        assert.equal(result.body.remaining, "60.00");
      }
      assert.equal((await report()).collections, "960.00");
      assert.equal((await report()).refunds, "40.00");
      const finish = await call(refundPath, "POST", { ...refund, amount: "60" }, ot, "final-refund", 1);
      assert.equal(finish.body.refund_status, "refunded");
      assert.equal(await db.collection("invoice_refunds").countDocuments({ invoice_id: invoiceId }), 2);
      const group = (await call("dashboard/consolidated", "GET", undefined, ot)).body;
      assert.equal(group.kpis.billed_revenue, "900.00");
      assert.equal(group.kpis.gross_collections, "1000.00");
      assert.equal(group.kpis.refunds, "100.00");
      assert.equal(group.kpis.collections, "900.00");
      assert.equal((await call("governance/refunds", "GET", undefined, ot, undefined, 1)).body.items.length, 0);
      const day = await call(
        "governance/closings",
        "POST",
        {
          branch_id: 1,
          business_date: new Intl.DateTimeFormat("en-CA", {
            timeZone: "Asia/Kolkata",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
          }).format(new Date()),
          opening_cash: "100",
        },
        ot,
        undefined,
        1,
      );
      assert.equal(day.status, 200);
      const submit = await call(
        `governance/closings/${day.body.id}/submit`,
        "POST",
        { counted_cash: "800" },
        ot,
        undefined,
        1,
      );
      assert.equal(submit.status, 200);
      assert.equal(submit.body.expected_cash, "800.00");
      assert.equal(submit.body.cash_collections, "800.00");
      assert.equal(submit.body.cash_refunds, "100.00");
      assert.equal(submit.body.variance, "0.00");
      assert.equal(submit.body.non_cash_total, "200.00");
      assert.equal(
        (
          await call(
            `governance/closings/${day.body.id}/close`,
            "POST",
            {},
            ot,
            undefined,
            1,
          )
        ).status,
        200,
      );
      assert.equal(
        (
          await call(
            "cafe/billing/pos/checkout",
            "POST",
            payload(1),
            ct,
            "closed-day-sale",
          )
        ).status,
        409,
      );
      const otherInvoice = (await db.collection("invoices").findOne({ company_id: 1, status: "paid" }))!;
      assert.equal((await call(`governance/voids/invoices/${otherInvoice.id}`, "POST", deletion, ot, "void-closed-day", 1)).status, 409);
      // Retail uses the same native financial engine with independent scope and numbering.
      const rc = await call(
        "categories",
        "POST",
        { name: "Retail stock" },
        ot,
        undefined,
        2,
      );
      const rs = await call(
        "suppliers",
        "POST",
        { name: "Retail supplier" },
        ot,
        undefined,
        2,
      );
      const rp = await call(
        "products",
        "POST",
        {
          name: "Retail item",
          sku: "RETAIL-ITEM",
          category_id: rc.body.id,
          supplier_id: rs.body.id,
          selling_price: "50.00",
          unit_cost: "20.00",
        },
        ot,
        undefined,
        2,
      );
      assert.equal(rp.status, 200);
      assert.equal(
        (
          await call(
            "inventory/adjustments",
            "POST",
            {
              branch_id: 2,
              product_id: rp.body.id,
              quantity_change: "10",
              reason: "Retail opening stock",
            },
            ot,
            undefined,
            2,
          )
        ).status,
        200,
      );
      for (const mode of [4, 5, 6]) {
        const body = {
          branch_id: 2,
          invoice_type: "non_gst",
          items: [{ product_id: rp.body.id, quantity: "1", discount: "0" }],
          payments: [{ payment_mode_id: mode, amount: "50.00" }],
        };
        const invoice = await call(
          "pos/checkout",
          "POST",
          body,
          rt,
          `retail-mode-${mode}`,
        );
        assert.equal(invoice.status, 200, JSON.stringify(invoice.body));
        assert.match(invoice.body.invoice_number, /^RETAIL-/);
        assert.equal(
          (await call("pos/checkout", "POST", body, rt, `retail-mode-${mode}`))
            .body.id,
          invoice.body.id,
        );
      }
      assert.equal(
        await db.collection("invoices").countDocuments({ company_id: 2 }),
        3,
      );
      assert.equal(
        (
          await db
            .collection("inventory")
            .findOne({ company_id: 2, product_id: rp.body.id })
        )?.quantity_scaled,
        700,
      );
      const mixed = await call("pos/checkout", "POST", {
        branch_id: 2, invoice_type: "non_gst",
        items: [{ product_id: rp.body.id, quantity: "1" }],
        payments: [{ payment_mode_id: 4, amount: "20" }, { payment_mode_id: 5, amount: "30", reference_number: "original-upi-ref" }],
      }, rt, "retail-mixed-payment");
      assert.equal(mixed.status, 200, JSON.stringify(mixed.body));
      const deleteMixed = await call(`governance/voids/invoices/${mixed.body.id}`, "POST", deletion, ot, "delete-retail-mixed", 2);
      assert.equal(deleteMixed.status, 200, JSON.stringify(deleteMixed.body));
      const retailCase = (await call("governance/refunds", "GET", undefined, ot, undefined, 2)).body.items[0];
      const cashLine = retailCase.payments.find((p: { cash: boolean }) => p.cash);
      const upiLine = retailCase.payments.find((p: { cash: boolean }) => !p.cash);
      const refundUpiPath = `governance/refunds/${retailCase.id}/payments/${upiLine.id}`;
      const refundUpi = { ...refund, refund_date: upiLine.received_date, amount: "30" };
      assert.equal((await call(refundUpiPath, "POST", refundUpi, ot, "upi-no-reference", 2)).status, 422);
      assert.equal((await call(refundUpiPath, "POST", { ...refundUpi, reference_number: "verified-upi-refund" }, ot, "upi-with-reference", 2)).status, 200);
      const correctCash = await call(`governance/refunds/${retailCase.id}/payments/${cashLine.id}`, "POST", {
        action: "not_received", confirmed: true, reason: "Cash was entered by mistake.",
      }, ot, "retail-no-cash-received", 2);
      assert.equal(correctCash.body.refund_status, "resolved", JSON.stringify(correctCash.body));
      const retailPayments = (await call("dashboard/overview", "GET", undefined, ot, undefined, 2)).body.kpis.payments;
      assert.deepEqual(retailPayments, { gross_collections: "180.00", refunds: "30.00", collections: "150.00" });

      // UTC is still January 31 at midnight on February 1 in Kolkata.
      const boundary = "2024-01-31T18:30:00.000Z";
      const beforeMidnight = "2024-01-31T18:29:59.999Z";
      const nextMidnight = "2024-02-01T18:30:00.000Z";
      const rows = [
        { id: 901, invoice_date: beforeMidnight, payment_date: boundary, grand_total: "10.00" },
        { id: 902, invoice_date: boundary, payment_date: nextMidnight, grand_total: "20.00" },
        { id: 903, invoice_date: nextMidnight, payment_date: nextMidnight, grand_total: "30.00" },
      ];
      for (const [companyId, productId] of [[1, product.body.id], [2, rp.body.id]]) {
        await db.collection("invoices").insertMany(rows.map((row) => ({
          id: companyId * 1000 + row.id,
          company_id: companyId,
          branch_id: companyId,
          invoice_number: `MIDNIGHT-${companyId}-${row.id}`,
          idempotency_key: `midnight-${companyId}-${row.id}`,
          public_id: `midnight-${companyId}-${row.id}`,
          source_type: companyId === 1 ? "cafe_takeaway" : "retail_pos",
          invoice_date: row.invoice_date,
          status: "issued",
          balance_due: "0.00",
          grand_total: row.grand_total,
          items: [{ product_id: productId, quantity: "1.00", line_total: row.grand_total }],
        })));
        await db.collection("invoice_payments").insertMany(rows.map((row) => ({
          id: companyId * 1000 + row.id,
          company_id: companyId,
          branch_id: companyId,
          invoice_id: companyId * 1000 + row.id,
          payment_datetime: row.payment_date,
          mode_type: "cash",
          mode_name: "Cash",
          amount: row.grand_total,
        })));
      }
      const query = "start_date=2024-02-01&end_date=2024-02-01";
      const get = async (path: string, venture?: number) => {
        const result = await call(path, "GET", undefined, ot, undefined, venture);
        assert.equal(result.status, 200, path + ": " + JSON.stringify(result.body));
        return result.body;
      };
      const cafe = await get(`dashboard/cafe?${query}`, 1);
      assert.equal(cafe.kpis.net_billed_revenue, "20.00");
      assert.equal(cafe.kpis.collections, "10.00");
      const history = await get(`cafe/billing/invoices?${query}`, 1);
      assert.deepEqual(history.items.map((row: { invoice_number: string }) => row.invoice_number), ["MIDNIGHT-1-902"]);
      const historyThroughDay = await get("cafe/billing/invoices?end_date=2024-02-01", 1);
      assert.equal(historyThroughDay.total, 2);
      const retailDay = await get(`sales/summary?${query}`, 2);
      assert.equal(retailDay.revenue, "20.00");
      assert.equal(retailDay.transaction_count, 1);
      const groupDay = await get(`dashboard/consolidated?${query}`);
      assert.equal(groupDay.kpis.billed_revenue, "40.00");
      assert.equal(groupDay.kpis.collections, "20.00");

      // The newest movement is out of range and must not consume the result limit.
      await db.collection("stock_movements").insertMany(rows.map((row) => ({
        id: row.id, company_id: 2, branch_id: 2, product_id: rp.body.id,
        created_at: row.invoice_date,
      })));
      const movements = await get(`inventory/movements?${query}&limit=1`, 2);
      assert.deepEqual(movements.map((row: { id: number }) => row.id), [902]);

      await db.collection("business_day_closures").insertOne({
        id: 901,
        company_id: 1,
        branch_id: 1,
        business_date: "2024-02-01",
        opening_cash: "100.00",
        status: "open",
      });
      const closedDay = await call("governance/closings/901/submit", "POST", {
        counted_cash: "110.00",
      }, ot, undefined, 1);
      assert.equal(closedDay.status, 200, JSON.stringify(closedDay.body));
      assert.equal(closedDay.body.cash_collections, "10.00");
      assert.equal(closedDay.body.expected_cash, "110.00");
      assert.equal(closedDay.body.variance, "0.00");

      // Old cancellations did not prove that money had moved. Recover their receipt
      // without changing a stored close; record an actual later refund on its date.
      await db.collection("invoices").updateOne({ id: 1901 }, { $set: { status: "cancelled" } });
      await db.collection("invoice_payments").updateOne({ id: 1901 }, { $set: { voided_at: boundary } });
      await db.collection("financial_reversals").insertOne({
        id: 991, company_id: 1, branch_id: 1, invoice_id: 1901, reversal_type: "void",
        refund_status: "not_processed_by_pos", amount: "10.00", created_at: boundary,
      });
      assert.equal((await get("governance/refunds", 1)).items[0].legacy, true);
      assert.equal((await get(`dashboard/cafe?${query}`, 1)).kpis.collections, "10.00");
      assert.equal((await call("governance/refunds/991/payments/1901", "POST", {
        ...refund, amount: "10", refund_date: "2024-02-01",
      }, ot, "closed-refund-day", 1)).status, 409);
      assert.equal((await call("governance/refunds/991/payments/1901", "POST", {
        ...refund, amount: "10", refund_date: "2024-02-03",
      }, ot, "verified-later-refund", 1)).status, 200);
      assert.equal((await get(`dashboard/cafe?${query}`, 1)).kpis.collections, "10.00");
      const later = "start_date=2024-02-03&end_date=2024-02-03";
      const laterGroup = await get(`dashboard/consolidated?${later}`);
      assert.equal(laterGroup.kpis.collections, "-10.00");
      assert.equal(laterGroup.payment_mode_mix.Cash, "-10.00");
      assert.equal((await get("governance/closings?branch_id=1&business_date=2024-02-01", 1)).cash_refunds, "0.00");

      assert.equal((await call("auth/logout", "POST", {}, ct)).status, 200);
      assert.equal((await call("auth/me", "GET", undefined, ct)).status, 401);
      await db
        .collection("users")
        .updateOne(
          { email: "owner@example.test" },
          { $set: { mfa_enabled: false } },
        );
      assert.equal((await call("auth/me", "GET", undefined, ot)).status, 403);
    } finally {
      await disconnect();
      await server.stop();
    }
  },
);
