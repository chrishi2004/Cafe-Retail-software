import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { handle } from "../src/server/handler";
import { totp } from "../src/server/security";
import { database, disconnect } from "../src/server/db";

test(
  "production Next browser: Cafe receipt flow and Retail barcode checkout",
  { timeout: 120000 },
  async () => {
    const mongo = await MongoMemoryReplSet.create({
      instanceOpts: [{ args: ["--nounixsocket"] }],
      replSet: { count: 1, storageEngine: "wiredTiger" },
    });
    Object.assign(process.env, {
      MONGODB_URI: mongo.getUri(),
      MONGODB_DB: "kalpvriksh_web_test_browser",
      AUTH_SECRET: "browser-only-auth-secret-with-at-least-32-characters",
      BOOTSTRAP_OWNER_EMAIL: "owner@example.test",
      BOOTSTRAP_OWNER_PASSWORD: "Owner-password-123!",
      BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@example.test",
      BOOTSTRAP_CAFE_CASHIER_PASSWORD: "Cafe-password-123!",
      BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test",
      BOOTSTRAP_RETAIL_CASHIER_PASSWORD: "Retail-password-123!",
    });
    let child: ReturnType<typeof spawn> | undefined;
    let browser;
    let log = "";
    try {
      const setup = await bootstrap();
      const { db } = await database();
      const now = new Date().toISOString();
      await db.collection("menu_items").insertOne({
        id: 1,
        company_id: 1,
        branch_id: 1,
        category_id: 1,
        public_id: "browser-sandwich",
        product_id: 1,
        name: "Browser Sandwich",
        selling_price: "100.00",
        available: true,
        is_active: true,
        version: 1,
        created_at: now,
        updated_at: now,
      });
      await db.collection("products").insertOne({
        id: 1,
        company_id: 1,
        name: "Browser Sandwich",
        sku: "BROWSER",
        selling_price: "100.00",
        unit_cost: "40.00",
        is_active: true,
      });
      await db.collection("inventory").insertOne({
        id: 1,
        company_id: 1,
        branch_id: 1,
        product_id: 1,
        quantity_scaled: 1000,
      });
      await db
        .collection("products")
        .insertOne({
          id: 2,
          company_id: 2,
          name: "Browser Retail Item",
          sku: "RETAIL-BROWSER",
          primary_barcode: "890000000001",
          selling_price: "50.25",
          unit_cost: "20.00",
          is_active: true,
        });
      await db
        .collection("inventory")
        .insertOne({
          id: 2,
          company_id: 2,
          branch_id: 2,
          product_id: 2,
          quantity_scaled: 1000,
        });
      await db
        .collection("menu_categories")
        .insertOne({
          id: 1,
          company_id: 1,
          branch_id: 1,
          public_id: "browser-menu",
          name: "Meals",
          is_active: true,
          display_order: 0,
        });
      const authResponse = await handle(
        new Request("http://localhost/api/auth/login", {
          method: "POST",
          body: JSON.stringify({
            email: "owner@example.test",
            password: "Owner-password-123!",
            recovery_code: setup.recoveryCodes[0],
          }),
        }),
        ["auth", "login"],
      );
      assert.equal(authResponse.status, 200);
      const ownerToken = (await authResponse.json()).access_token;
      const fixture = async (path: string, body: unknown) => {
        const response = await handle(
          new Request("http://localhost/api/" + path, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${ownerToken}`,
              "X-Venture-Id": "1",
            },
            body: JSON.stringify(body),
          }),
          path.split("/"),
        );
        assert.equal(response.status, 200, await response.clone().text());
        return response.json();
      };
      const table = await fixture("cafe/tables", {
        branch_id: 1,
        table_code: "WEB",
        display_name: "Browser table",
      });
      await fixture("cafe/table-sessions", { table_id: table.id });
      const qr = await fixture(`cafe/tables/${table.id}/qr/rotate`, {});
      child = spawn(
        process.execPath,
        [
          resolve("node_modules/next/dist/bin/next"),
          "start",
          "--hostname",
          "127.0.0.1",
          "--port",
          "4317",
        ],
        {
          env: { ...process.env, NODE_ENV: "production" },
          stdio: ["ignore", "pipe", "pipe"],
        },
      );
      child.stdout?.on("data", (chunk) => (log += String(chunk)));
      child.stderr?.on("data", (chunk) => (log += String(chunk)));
      let ready = false;
      for (let attempt = 0; attempt < 80; attempt++) {
        try {
          const response = await fetch("http://127.0.0.1:4317/api/health");
          if (response.ok) {
            ready = true;
            break;
          }
        } catch {}
        await new Promise((r) => setTimeout(r, 100));
      }
      assert(ready, log);
      browser = await chromium.launch({
        headless: true,
        args: ["--no-sandbox"],
      });
      const page = await browser.newPage();
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto("http://127.0.0.1:4317/login");
      await page.getByLabel("Email", { exact: true }).fill("cafe@example.test");
      await page
        .getByLabel("Password", { exact: true })
        .fill("Cafe-password-123!");
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await page.waitForURL("**/cafe/pos");
      await page.getByRole("button", { name: /Browser Sandwich.*100/ }).click();
      await page.getByRole("button", { name: "Pay & create invoice" }).click();
      await page
        .getByRole("article", { name: /Receipt CAFE-/ })
        .first()
        .waitFor();
      assert.equal(await db.collection("invoices").countDocuments(), 1);
      assert.equal(await db.collection("invoice_payments").countDocuments(), 1);
      assert.equal(
        (await db.collection("inventory").findOne({ id: 1 }))?.quantity_scaled,
        900,
      );
      await page.emulateMedia({ media: "print" });
      const printState = await page.evaluate(() => ({
        ready: document.body.classList.contains("cafe-receipt-ready"),
        paper: !!document.querySelector(".cafe-receipt-paper"),
        navigation: [...document.querySelectorAll("nav")].every(
          (el) => el.getClientRects().length === 0,
        ),
      }));
      assert(printState.ready && printState.paper);
      assert(printState.navigation);
      await page.emulateMedia({ media: "screen" });
      await page
        .getByRole("button", { name: "Next customer", exact: true })
        .click();
      await page.getByText("Select menu items to start.").waitFor();
      await page.getByRole("button", { name: /Log ?out|Sign out/i }).click();
      await page
        .getByRole("heading", { name: "Sign in to your workspace" })
        .waitFor();
      assert.equal(
        await db.collection("business_day_closures").countDocuments(),
        0,
      );
      await page
        .getByLabel("Email", { exact: true })
        .fill("retail@example.test");
      await page
        .getByLabel("Password", { exact: true })
        .fill("Retail-password-123!");
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await page.waitForURL("**/retail/pos");
      await page
        .getByLabel("Barcode, SKU, or product name")
        .fill("890000000001");
      await page.getByLabel("Barcode, SKU, or product name").press("Enter");
      await page
        .getByRole("button", { name: "Cash checkout", exact: true })
        .click();
      await page
        .getByRole("heading", { name: "RETAIL-000001", exact: true })
        .waitFor();
      assert.equal(
        await db.collection("invoices").countDocuments({ company_id: 2 }),
        1,
      );
      assert.equal(
        (await db.collection("invoices").findOne({ company_id: 2 }))
          ?.grand_total,
        "50.25",
      );
      assert.equal(
        (await db.collection("inventory").findOne({ id: 2 }))?.quantity_scaled,
        900,
      );
      await page.emulateMedia({ media: "print" });
      assert(
        await page.evaluate(() =>
          document.body.classList.contains("cafe-receipt-ready"),
        ),
      );
      await page.emulateMedia({ media: "screen" });
      await page.getByRole("button", { name: /Log ?out|Sign out/i }).click();
      await page
        .getByLabel("Email", { exact: true })
        .fill("owner@example.test");
      await page
        .getByLabel("Password", { exact: true })
        .fill("Owner-password-123!");
      await page
        .getByLabel("Authenticator code", { exact: true })
        .fill(totp(setup.totpSecret));
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await page.waitForURL("**/super-admin/ventures");
      await page
        .getByRole("button", { name: "Open Retail workspace", exact: true })
        .click();
      await page.waitForURL("**/retail/overview");
      const failedApis: string[] = [];
      page.on("response", (response) => {
        if (response.url().includes("/api/") && response.status() >= 400)
          failedApis.push(
            `${response.status()} ${new URL(response.url()).pathname}`,
          );
      });
      const screens = [
        ["inventory", "Inventory and stock ledger"],
        ["purchase-orders", "Purchase orders"],
        ["forecasting", "Forecasting"],
        ["settings", "Settings"],
        ["closing", "Retail cash reconciliation"],
      ];
      for (const [route, title] of screens) {
        await page.goto("http://127.0.0.1:4317/retail/" + route);
        await page.getByRole("heading", { name: title, exact: true }).waitFor();
        await page.waitForLoadState("networkidle");
        assert.equal(
          await page
            .getByText(
              /migration_pending|has not passed native|could not complete/i,
            )
            .count(),
          0,
          route,
        );
      }
      await page.screenshot({
        path: "/tmp/nextjs-inventory-owner.png",
        fullPage: true,
      });
      assert.deepEqual(failedApis, []);
      const guestPage = await browser.newPage();
      guestPage.on("pageerror", (e) => errors.push(e.message));
      await guestPage.goto("http://127.0.0.1:4317/order/" + qr.raw_token);
      await guestPage
        .getByRole("heading", { name: "Browser table", exact: true })
        .waitFor();
      await guestPage.getByRole("button", { name: "Add", exact: true }).click();
      await guestPage.getByRole("button", { name: /Place order/ }).click();
      await guestPage
        .getByText(/Order .* confirmed/i)
        .first()
        .waitFor();
      assert.equal(
        await db
          .collection("cafe_orders")
          .countDocuments({ source_channel: "qr_customer" }),
        1,
      );
      assert.equal(
        await db.collection("invoices").countDocuments(),
        2,
        "Guest order must not create an invoice.",
      );
      await guestPage.close();
      assert.deepEqual(errors, []);
    } finally {
      await browser?.close();
      child?.kill("SIGTERM");
      if (child)
        await new Promise<void>((resolve) => {
          if (child!.exitCode !== null) return resolve();
          child!.once("exit", () => resolve());
        });
      await disconnect();
      await mongo.stop();
    }
  },
);
