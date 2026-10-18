import test from "node:test";
import assert from "node:assert/strict";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";
import { totp } from "../src/server/security";
import { businessDate } from "../src/server/money";

test(
  "Retail reports, purchasing, partial receiving, customer credit, GST and draft issue use native transactions",
  { timeout: 180000 },
  async () => {
    const server = await MongoMemoryReplSet.create({
      instanceOpts: [{ args: ["--nounixsocket"] }],
      replSet: { count: 1, storageEngine: "wiredTiger" },
    });
    Object.assign(process.env, {
      MONGODB_URI: server.getUri(),
      MONGODB_DB: "kalpvriksh_web_retail_workflows",
      AUTH_SECRET: "test-only-32-character-auth-secret-value",
      BOOTSTRAP_OWNER_EMAIL: "owner@test.example",
      BOOTSTRAP_OWNER_PASSWORD: "Owner-123-password",
      BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@test.example",
      BOOTSTRAP_CAFE_CASHIER_PASSWORD: "Cafe-123-password",
      BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@test.example",
      BOOTSTRAP_RETAIL_CASHIER_PASSWORD: "Retail-123-password",
    });
    try {
      const setup = await bootstrap();
      let token = "",
        venture: number | undefined;
      const call = async (
        path: string,
        method = "GET",
        body?: unknown,
        key?: string,
      ) => {
        const response = await handle(
          new Request(`http://localhost/api/${path}`, {
            method,
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
              ...(venture ? { "X-Venture-Id": String(venture) } : {}),
              ...(key ? { "Idempotency-Key": key } : {}),
            },
            body: body === undefined ? undefined : JSON.stringify(body),
          }),
          path.split("?")[0].split("/"),
        );
        return { status: response.status, body: await response.json() };
      };
      const ok = async (
        path: string,
        method = "GET",
        body?: unknown,
        key?: string,
      ) => {
        const r = await call(path, method, body, key);
        assert.equal(r.status, 200, `${path}: ${JSON.stringify(r.body)}`);
        return r.body;
      };
      token = (
        await ok("auth/login", "POST", {
          email: "owner@test.example",
          password: "Owner-123-password",
          totp_code: totp(setup.totpSecret),
        })
      ).access_token;
      venture = 2;
      for (const path of [
        "dashboard/inventory",
        "dashboard/overview",
        "dashboard/sales",
        "dashboard/purchase-orders",
      ]) {
        const empty = await ok(path);
        assert.equal(empty.period_end, businessDate());
      }
      const category = await ok("categories", "POST", {
          name: "Retail category",
        }),
        supplier = await ok("suppliers", "POST", { name: "Retail supplier" });
      const product = await ok("products", "POST", {
        name: "Product",
        sku: "RET-1",
        category_id: category.id,
        supplier_id: supplier.id,
        selling_price: "100.00",
        unit_cost: "40.00",
        reorder_threshold: "5",
        target_stock_level: "20",
      });
      const po = await ok("purchase-orders", "POST", {
        supplier_id: supplier.id,
        branch_id: 2,
        items: [{ product_id: product.id, quantity_ordered: "10" }],
      });
      await ok(`purchase-orders/${po.id}/submit`, "POST", {});
      await ok(`purchase-orders/${po.id}/approve`, "POST", {});
      await ok(`purchase-orders/${po.id}/mark-ordered`, "POST", {});
      assert.equal((await ok("inventory"))[0].quantity_on_order, "10.00");
      const part = await ok(`purchase-orders/${po.id}/receive`, "POST", {
        items: [{ item_id: po.items[0].id, quantity_received: "4" }],
      });
      assert.equal(part.status, "partially_received");
      const over = await call(`purchase-orders/${po.id}/receive`, "POST", {
        items: [{ item_id: po.items[0].id, quantity_received: "7" }],
      });
      assert.equal(over.status, 422);
      await ok(`purchase-orders/${po.id}/receive`, "POST", {
        items: [{ item_id: po.items[0].id, quantity_received: "6" }],
      });
      assert.equal((await ok("inventory"))[0].quantity_on_hand, "10.00");
      assert.equal((await ok("inventory"))[0].quantity_on_order, "0.00");
      assert.equal(
        (
          await call(`purchase-orders/${po.id}/receive`, "POST", {
            items: [{ item_id: po.items[0].id, quantity_received: "1" }],
          })
        ).status,
        409,
      );
      const customer = await ok("customers", "POST", {
        name: "Customer",
        branch_id: 2,
        credit_limit: "500",
        opening_balance: "20",
      });
      const cart = {
        branch_id: 2,
        customer_id: customer.id,
        invoice_type: "non_gst",
        items: [{ product_id: product.id, quantity: "2", discount: "0" }],
        payments: [{ payment_mode_id: 4, amount: "50" }],
      };
      const sale = await ok("pos/checkout", "POST", cart, "credit-sale-key");
      assert.equal(sale.balance_due, "150.00");
      const ledger = await ok(`customers/${customer.id}/ledger`);
      assert.equal(ledger.at(-1).running_balance, "170.00");
      const pay = { payment_mode_id: 5, amount: "150" };
      const duplicates = await Promise.all([
        call(
          `invoices/${sale.id}/payments`,
          "POST",
          pay,
          "invoice-collection-key",
        ),
        call(
          `invoices/${sale.id}/payments`,
          "POST",
          pay,
          "invoice-collection-key",
        ),
      ]);
      assert(
        duplicates.every((x) => x.status === 200),
        JSON.stringify(duplicates),
      );
      assert.equal(duplicates[0].body.balance_due, "0.00");
      assert.equal(
        (await ok(`customers/${customer.id}/ledger`)).at(-1).running_balance,
        "20.00",
      );
      assert.equal(
        (await ok("dashboard/inventory")).summary.current_stock_value,
        "320.00",
      );
      assert.equal((await ok("dashboard/sales")).summary.revenue, "200.00");
      venture = 1;
      assert.equal((await ok("dashboard/sales")).summary.revenue, "0.00");
      assert.equal((await call(`purchase-orders/${po.id}`)).status, 404);
      venture = 2;
      const draft = await ok("invoices", "POST", {
        branch_id: 2,
        invoice_type: "non_gst",
        items: [{ product_id: product.id, quantity: "1", discount: "0" }],
      });
      assert.equal(draft.status, "draft");
      const issued = await ok(
        `invoices/${draft.id}/issue`,
        "POST",
        { payments: [{ payment_mode_id: 4, amount: "100" }] },
        "draft-issue-key",
      );
      assert.equal(issued.id, draft.id);
      assert.equal(issued.status, "paid");
      const legacySale = await ok(
        "sales",
        "POST",
        {
          branch_id: 2,
          tax_rate: "0",
          items: [
            { product_id: product.id, quantity: "1", discount_amount: "0" },
          ],
        },
        "legacy-cash-sale",
      );
      assert.equal(legacySale.tax_total, "0.00");
      const rate = await ok("tax-rates", "POST", {
        name: "GST 18%",
        rate_percent: "18",
        cess_percent: "0",
      });
      await ok(`products/${product.id}`, "PUT", {
        gst_rate_id: rate.id,
        hsn_sac_code: "1234",
      });
      await ok("business-profile", "PUT", {
        legal_name: "Retail Legal",
        gstin: "29ABCDE1234F1Z5",
        state_code: "29",
        state: "Karnataka",
      });
      await ok("invoice-sequences", "POST", {
        branch_id: 2,
        invoice_type: "gst_invoice",
        prefix: "GST-",
        next_number: 1,
        padding: 6,
        reset_rule: "never",
      });
      await ok("tax-operation/settings", "PUT", {
        tax_registration_status: "registered",
        customer_details_on_bill: "basic",
        registration_active: true,
        registration_id: 2,
      });
      await ok("auth/step-up", "POST", {
        password: "Owner-123-password",
        totp_code: totp(setup.totpSecret),
      });
      await ok("tax-operation/activate-gst", "POST", {
        effective_from: businessDate(),
        acknowledge_professional_review: true,
        confirmation: "ACTIVATE GST",
      });
      const gstCart = {
        branch_id: 2,
        invoice_type: "gst",
        place_of_supply_state_code: "29",
        items: [{ product_id: product.id, quantity: "1", discount: "0" }],
        payments: [{ payment_mode_id: 4, amount: "118" }],
      };
      const gst = await ok("pos/checkout", "POST", gstCart, "gst-checkout-key");
      assert.equal(gst.cgst_total, "9.00");
      assert.equal(gst.sgst_total, "9.00");
      assert.equal(gst.grand_total, "118.00");
      assert.match(gst.invoice_number, /^GST-/);
      const interstate = await ok("pos/quote", "POST", {
        ...gstCart,
        place_of_supply_state_code: "27",
      });
      assert.equal(interstate.igst_total, "18.00");
      assert.equal(interstate.cgst_total, "0.00");
      const retail = (
        await ok("auth/login", "POST", {
          email: "retail@test.example",
          password: "Retail-123-password",
        })
      ).access_token;
      token = retail;
      venture = undefined;
      assert.equal(
        (await call(`purchase-orders/${po.id}/approve`, "POST", {})).status,
        403,
      );
      assert.equal((await call("dashboard/inventory?branch_id=1")).status, 404);
      const { db } = await database();
      assert.equal(
        await db
          .collection("invoice_payments")
          .countDocuments({ invoice_id: sale.id }),
        2,
      );
    } finally {
      await disconnect();
      await server.stop();
    }
  },
);
