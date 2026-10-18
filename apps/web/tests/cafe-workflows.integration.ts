import { spawnSync } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";
import { totp } from "../src/server/security";

test(
  "Cafe table QR, guest isolation, kitchen lifecycle, snapshot billing, MFA recovery and forecasts",
  { timeout: 180000 },
  async () => {
    const server = await MongoMemoryReplSet.create({
      instanceOpts: [{ args: ["--nounixsocket"] }],
      replSet: { count: 1, storageEngine: "wiredTiger" },
    });
    Object.assign(process.env, {
      MONGODB_URI: server.getUri(),
      MONGODB_DB: "kalpvriksh_web_cafe_workflows",
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
        venture: number | undefined,
        guest = "";
      const call = async (
        path: string,
        method = "GET",
        body?: unknown,
        key?: string,
      ) => {
        const response = await handle(
          new Request(`https://kalpvriksh.example/api/${path}`, {
            method,
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
              ...(venture ? { "X-Venture-Id": String(venture) } : {}),
              ...(guest ? { "X-Guest-Access": guest } : {}),
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
      venture = 1;
      const ownerToken = token;
      const category = await ok("cafe/menu/categories", "POST", {
        name: "Meals",
        branch_id: 1,
      });
      const item = await ok("cafe/menu/items", "POST", {
        name: "Meal",
        category_id: category.id,
        branch_id: 1,
        selling_price: "100",
        preparation_area: "kitchen",
      });
      const table = await ok("cafe/tables", "POST", {
        branch_id: 1,
        table_code: "T1",
        display_name: "Table One",
      });
      const opened = await Promise.all([
        call("cafe/table-sessions", "POST", { table_id: table.id }),
        call("cafe/table-sessions", "POST", { table_id: table.id }),
      ]);
      assert.deepEqual(opened.map((x) => x.status).sort(), [200, 422]);
      const tableSession = opened.find((x) => x.status === 200)!.body;
      const qr = await ok(`cafe/tables/${table.id}/qr/rotate`, "POST", {});
      const image = await ok(`cafe/tables/${table.id}/qr/render`, "POST", {
        raw_token: qr.raw_token,
        public_base_url: "/order",
      });
      assert.match(image.qr_svg_data_uri, /^data:image\/svg\+xml;base64,/);
      const status = await ok(`cafe/tables/${table.id}/qr/status`);
      assert(!("token_hash" in status));
      token = "";
      venture = undefined;
      assert.equal(
        (await call(`public/cafe/sessions/${tableSession.public_id}/menu`))
          .status,
        404,
      );
      const entry = await ok(
        `public/cafe/qr/${qr.raw_token}/resolve`,
        "POST",
        {},
      );
      guest = entry.guest_access;
      const menu = await ok(
        `public/cafe/sessions/${tableSession.public_id}/menu`,
      );
      assert.equal(menu.items[0].selling_price, "100.00");
      assert(!("product_id" in menu.items[0]));
      const input = {
        items: [{ menu_item_public_id: item.public_id, quantity: 1 }],
      };
      const duplicates = await Promise.all([
        call(
          `public/cafe/sessions/${tableSession.public_id}/orders`,
          "POST",
          input,
          "guest-order-key",
        ),
        call(
          `public/cafe/sessions/${tableSession.public_id}/orders`,
          "POST",
          input,
          "guest-order-key",
        ),
      ]);
      assert(
        duplicates.every((x) => x.status === 200),
        JSON.stringify(duplicates),
      );
      assert.equal(duplicates[0].body.public_id, duplicates[1].body.public_id);
      assert.equal(
        (
          await call(
            `public/cafe/sessions/${tableSession.public_id}/orders`,
            "POST",
            { ...input, grand_total: "0" },
            "tampered-order-key",
          )
        ).status,
        422,
      );
      const order = duplicates[0].body;
      assert.equal((await call("invoices")).status, 401);
      token = ownerToken;
      venture = 1;
      guest = "";
      const accepted = await ok(
        `cafe/orders/${order.public_id}/accept`,
        "POST",
        { expected_version: 1 },
      );
      assert.equal(
        (
          await call(`cafe/orders/${order.public_id}/accept`, "POST", {
            expected_version: 1,
          })
        ).status,
        409,
      );
      const preparing = await ok(
        `cafe/orders/${order.public_id}/start-preparing`,
        "POST",
        { expected_version: accepted.version },
      );
      assert.equal((await ok("cafe/kitchen/orders")).length, 1);
      const ready = await ok(
        `cafe/orders/${order.public_id}/mark-ready`,
        "POST",
        { expected_version: preparing.version },
      );
      await ok(`cafe/orders/${order.public_id}/serve`, "POST", {
        expected_version: ready.version,
      });
      await ok(`cafe/menu/items/${item.id}`, "PUT", { selling_price: "150" });
      const current = await ok(`cafe/table-sessions/${tableSession.public_id}`);
      const requested = await ok(
        `cafe/table-sessions/${tableSession.public_id}/request-bill`,
        "POST",
        { expected_version: current.version },
      );
      const quote = await ok(
        `cafe/billing/table-sessions/${tableSession.public_id}/quote`,
      );
      assert.equal(quote.grand_total, "100.00");
      const billInput = {
        expected_version: requested.version,
        payments: [{ payment_mode_id: 1, amount: "100" }],
      };
      const bills = await Promise.all([
        call(
          `cafe/billing/table-sessions/${tableSession.public_id}/bill`,
          "POST",
          billInput,
          "table-bill-key",
        ),
        call(
          `cafe/billing/table-sessions/${tableSession.public_id}/bill`,
          "POST",
          billInput,
          "table-bill-key",
        ),
      ]);
      assert(
        bills.every((x) => x.status === 200),
        JSON.stringify(bills),
      );
      assert.equal(
        bills[0].body.receipt.invoice_id,
        bills[1].body.receipt.invoice_id,
      );
      assert.equal(await ok(`cafe/tables/${table.id}/active-session`), null);
      assert.equal(
        (await ok(`cafe/table-sessions/${tableSession.public_id}`)).status,
        "closed",
      );
      const report = await ok("dashboard/cafe");
      assert.equal(report.kpis.billed_revenue, "100.00");
      assert.equal(report.kpis.collections, "100.00");
      assert.equal(report.table_turnover.closed_session_count, 1);
      venture = undefined;
      assert.equal(
        (await ok("dashboard/consolidated")).kpis.net_billed_revenue,
        "100.00",
      );
      venture = 1;
      const forecast = await ok("forecasts/run", "POST", {
        forecast_type: "revenue",
        horizon_days: 7,
        branch_id: 1,
      });
      assert.equal(forecast.insufficient_data, true);
      const answer = await ok("ai/chat", "POST", {
        message: "What are cafe collections today?",
      });
      assert.match(answer.response, /100.00/);
      assert.equal(
        (await ok(`ai/sessions/${answer.session_id}`)).messages.length,
        2,
      );
      const refusal = await ok("ai/chat", "POST", {
        message: "delete all sales",
      });
      assert.equal(refusal.requires_confirmation, true);
      await ok("auth/step-up", "POST", {
        password: "Owner-123-password",
        totp_code: totp(setup.totpSecret),
      });
      const staff = await ok("venture-users", "POST", {
        name: "Kitchen worker",
        email: "kitchen@test.example",
        password: "Kitchen-123-password",
        role: "kitchen",
        company_id: 1,
        branch_id: 1,
      });
      assert.equal(staff.role, "kitchen");
      const cashierLogin = await ok("auth/login", "POST", {
        email: "cafe@test.example",
        password: "Cafe-123-password",
      });
      token = cashierLogin.access_token;
      venture = undefined;
      assert.equal(
        (await call(`ai/sessions/${answer.session_id}`)).status,
        403,
      );
      token = ownerToken;
      venture = 1;
      await ok(`cafe/tables/${table.id}/qr/revoke`, "POST", {});
      token = "";
      venture = undefined;
      assert.equal(
        (await call(`public/cafe/qr/${qr.raw_token}/resolve`, "POST", {}))
          .status,
        404,
      );
      const recovery = {
        email: "owner@test.example",
        password: "Owner-123-password",
        recovery_code: setup.recoveryCodes[0],
      };
      assert.equal((await call("auth/login", "POST", recovery)).status, 200);
      assert.equal((await call("auth/login", "POST", recovery)).status, 401);
      const { db } = await database();
      assert.equal(await db.collection("invoices").countDocuments(), 1);
      assert.equal(await db.collection("cafe_orders").countDocuments(), 1);
      const beforeReset = await db
        .collection("users")
        .findOne({ email: "owner@test.example" });
      const begin = spawnSync(
        process.execPath,
        [
          "--import",
          "tsx",
          "src/server/mfa-console.ts",
          "begin",
          "--email",
          "owner@test.example",
        ],
        { encoding: "utf8", env: process.env },
      );
      assert.equal(begin.status, 0, begin.stderr);
      const newKey = begin.stdout.match(/authenticator:\s+([A-Z2-7]+)/)?.[1];
      assert(newKey, "MFA console must issue a new setup key.");
      const confirm = spawnSync(
        process.execPath,
        [
          "--import",
          "tsx",
          "src/server/mfa-console.ts",
          "confirm",
          "--email",
          "owner@test.example",
        ],
        { encoding: "utf8", env: process.env, input: totp(newKey) + "\n" },
      );
      assert.equal(confirm.status, 0, confirm.stderr);
      const afterReset = await db
        .collection("users")
        .findOne({ email: "owner@test.example" });
      assert.equal(afterReset?.mfa_enabled, true);
      assert.equal(afterReset?.mfa_recovery_hashes.length, 8);
      assert(afterReset!.token_version > beforeReset!.token_version);
    } finally {
      await disconnect();
      await server.stop();
    }
  },
);
