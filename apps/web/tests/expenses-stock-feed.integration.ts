import test from "node:test";
import assert from "node:assert/strict";
import { MongoMemoryReplSet } from "mongodb-memory-server";

import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";
import { businessDate } from "../src/server/money";
import { totp } from "../src/server/security";

test(
  "Cafe stock feed and branch expenses reconcile inventory and daily closing",
  { timeout: 180000 },
  async () => {
    const server = await MongoMemoryReplSet.create({
      instanceOpts: [{ args: ["--nounixsocket"] }],
      replSet: { count: 1, storageEngine: "wiredTiger" },
    });
    Object.assign(process.env, {
      MONGODB_URI: server.getUri(),
      MONGODB_DB: "kalpvriksh_web_expenses_stock_feed",
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
      let token = "";
      let venture: number | undefined = 1;
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
        const result = await call(path, method, body, key);
        assert.equal(result.status, 200, `${path}: ${JSON.stringify(result.body)}`);
        return result.body;
      };

      token = (
        await ok("auth/login", "POST", {
          email: "owner@test.example",
          password: "Owner-123-password",
          totp_code: totp(setup.totpSecret),
        })
      ).access_token;

      const secondBranch = await ok("branches", "POST", {
        name: "Cafe Second Shop",
        address: "Second shop",
        city: "Bengaluru",
      });
      const category = await ok("categories", "POST", {
        name: "Raw Materials",
        description: "Cafe grocery and consumable stock",
      });
      const supplier = await ok("suppliers", "POST", {
        name: "Local Market",
        lead_time_days: 0,
      });
      const product = await ok("products", "POST", {
        name: "Tomatoes",
        sku: "CAFE-TOMATO",
        category_id: category.id,
        supplier_id: supplier.id,
        unit_of_measure: "kg",
        selling_price: "0",
        unit_cost: "50",
        reorder_threshold: "2",
        target_stock_level: "10",
        item_type: "goods",
      });

      const stockPayload = {
        branch_id: 1,
        supplier_id: supplier.id,
        purchase_date: businessDate(),
        payment_mode: "cash",
        record_expense: true,
        reference_number: "MARKET-001",
        items: [{ product_id: product.id, quantity: "5", unit_cost: "50" }],
      };
      const intake = await ok(
        "cafe/stock-intakes",
        "POST",
        stockPayload,
        "stock-feed-test-key",
      );
      const replay = await ok(
        "cafe/stock-intakes",
        "POST",
        stockPayload,
        "stock-feed-test-key",
      );
      assert.equal(replay.id, intake.id);
      assert(intake.expense_id);

      const inventory = await ok("inventory?branch_id=1");
      assert.equal(inventory.find((row: any) => row.product_id === product.id)?.quantity_on_hand, "5.00");

      await ok("expenses", "POST", {
        branch_id: 1,
        expense_date: businessDate(),
        category: "maintenance",
        description: "Mixer repair",
        amount: "100",
        payment_mode: "cash",
        vendor_name: "Repair Shop",
      });

      await ok("expenses", "POST", {
        branch_id: secondBranch.id,
        expense_date: businessDate(),
        category: "utilities",
        description: "Internet",
        amount: "50",
        payment_mode: "upi",
      });

      const branchOneSummary = await ok(
        `expenses/summary?branch_id=1&start_date=${businessDate()}&end_date=${businessDate()}`,
      );
      assert.equal(branchOneSummary.total_expenses, "350.00");
      assert.equal(branchOneSummary.cash_expenses, "350.00");
      assert.equal(branchOneSummary.stock_purchase_expenses, "250.00");

      const branchTwoSummary = await ok(
        `expenses/summary?branch_id=${secondBranch.id}&start_date=${businessDate()}&end_date=${businessDate()}`,
      );
      assert.equal(branchTwoSummary.total_expenses, "50.00");
      assert.equal(branchTwoSummary.cash_expenses, "0.00");
      assert.equal(branchTwoSummary.non_cash_expenses, "50.00");

      const closing = await ok("governance/closings", "POST", {
        branch_id: 1,
        business_date: businessDate(),
        opening_cash: "500",
      });
      const submitted = await ok(
        `governance/closings/${closing.id}/submit`,
        "POST",
        { counted_cash: "150" },
      );
      assert.equal(submitted.cash_expenses, "350.00");
      assert.equal(submitted.expected_cash, "150.00");
      assert.equal(submitted.variance, "0.00");

      assert.equal(
        (
          await call("expenses", "POST", {
            branch_id: 1,
            expense_date: businessDate(),
            category: "maintenance",
            description: "Late expense",
            amount: "10",
            payment_mode: "cash",
          })
        ).status,
        409,
      );

      venture = 2;
      assert.equal((await ok("expenses")).length, 0);

      const { db } = await database();
      assert.equal(
        await db.collection("stock_intakes").countDocuments({ company_id: 1 }),
        1,
      );
      assert.equal(
        await db.collection("stock_movements").countDocuments({
          company_id: 1,
          movement_type: "stock_intake",
          reference_id: intake.id,
        }),
        1,
      );
      assert.equal(
        await db.collection("expenses").countDocuments({
          company_id: 1,
          source_type: "stock_intake",
          source_id: intake.id,
        }),
        1,
      );
    } finally {
      await disconnect();
      await server.stop();
    }
  },
);
