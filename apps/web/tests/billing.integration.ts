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
        { counted_cash: "900" },
        ot,
        undefined,
        1,
      );
      assert.equal(submit.status, 200);
      assert.equal(submit.body.expected_cash, "900.00");
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
