import assert from "node:assert/strict";
import test from "node:test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";

test("owner audit is scoped, paged across concurrent inserts, redacted and bounded by IST dates", { timeout: 120000 }, async () => {
  const mongo = await MongoMemoryReplSet.create({ instanceOpts: [{ args: ["--nounixsocket"] }], replSet: { count: 1, storageEngine: "wiredTiger" } });
  const password = "Audit-test-only-password!";
  Object.assign(process.env, {
    MONGODB_URI: mongo.getUri(), MONGODB_DB: "kalpvriksh_web_test_audit", AUTH_SECRET: "audit-only-test-secret-at-least-32-chars",
    BOOTSTRAP_OWNER_EMAIL: "owner@example.test", BOOTSTRAP_OWNER_PASSWORD: password,
    BOOTSTRAP_CAFE_CASHIER_EMAIL: "staff@example.test", BOOTSTRAP_CAFE_CASHIER_PASSWORD: password,
    BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test", BOOTSTRAP_RETAIL_CASHIER_PASSWORD: password,
  });
  try {
    const setup = await bootstrap();
    const { db } = await database();
    const call = (route: string, token?: string, method = "GET", body?: object) => handle(new Request(`http://localhost/api/${route}`, {
      method, headers: token ? { Authorization: `Bearer ${token}` } : {}, body: body ? JSON.stringify(body) : undefined,
    }), route.split("?")[0].split("/"));
    const ownerLogin = await call("auth/login", undefined, "POST", { email: "owner@example.test", password, recovery_code: setup.recoveryCodes[0] });
    const staffLogin = await call("auth/login", undefined, "POST", { email: "staff@example.test", password });
    assert.equal(ownerLogin.status, 200);
    assert.equal(staffLogin.status, 200);
    const { access_token: owner, user } = await ownerLogin.json();
    const { access_token: staff } = await staffLogin.json();
    assert.equal((await call("audit/events", staff)).status, 403);
    assert.equal((await call("audit/options", staff)).status, 403);
    assert.equal((await call("audit/events?format=csv", staff)).status, 403);
    assert.equal((await call("audit/events", owner, "DELETE")).status, 405);

    await db.collection("companies").insertOne({ id: 99, business_group_id: 99, name: "External venture" });
    await db.collection("branches").insertOne({ id: 99, company_id: 99, name: "External branch" });
    const collection = db.collection("audit_events");
    const sameInstant = "2025-03-31T18:30:00.000Z";
    const common = {
      created_at: sameInstant, actor_id: user.id, actor_name: "=SUM(1,2)", action: "void", entity_type: "invoice",
      record_reference: "CAFE-001", entity_id: 1234, outcome: "recorded",
      details: { branch_id: 1, reversal_id: 88, token: "must-never-export", reason: "must-never-export", prior_snapshot: { password: "must-never-export" } },
    };
    await Promise.all([
      collection.insertOne({ ...common, id: 1, company_id: 1, created_at: "2025-03-31T18:29:59.999Z" }),
      collection.insertOne({ ...common, id: 2, company_id: 1 }),
      collection.insertOne({ ...common, id: 3, company_id: 1, business_group_id: 1 }),
      collection.insertOne({ ...common, id: 4, company_id: 2, branch_id: 2 }),
      collection.insertOne({ ...common, id: 5, company_id: 99, business_group_id: 99 }),
      collection.insertOne({ ...common, id: 6, company_id: 1, business_group_id: 99 }),
      collection.insertOne({ ...common, id: 7, company_id: null, business_group_id: 99 }),
      collection.insertOne({ ...common, id: 8, company_id: 1, action: "update", entity_type: "expense", record_reference: "OTHER-001" }),
    ]);
    const range = "start_date=2025-04-01&end_date=2025-04-01";
    const selection = `audit/events?${range}&company_id=1&branch_id=1&category=cancellations&reference=cafe-001&actor_id=${user.id}`;
    const response = await call(selection + "&limit=1", owner);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    const first = await response.json();
    assert.deepEqual(first.rows.map((r: { id: number }) => r.id), [3]);
    assert.match(first.rows[0].timestamp_ist, /1 Apr 2025.*12:00:00.*IST/);
    assert.equal(first.rows[0].action, "Voided");
    assert.equal(first.rows[0].outcome, "Recorded");
    assert(!JSON.stringify(first).includes("must-never-export"));
    assert(first.next_cursor);

    await collection.insertOne({ ...common, id: 9, company_id: 1 });
    const next = await (await call(selection + "&cursor=" + first.next_cursor, owner)).json();
    assert.deepEqual(next.rows.map((r: { id: number }) => r.id), [2]);
    assert.equal(next.next_cursor, null);
    const broader = await (await call(`audit/events?${range}`, owner)).json();
    assert.deepEqual(broader.rows.map((r: { id: number }) => r.id), [9, 8, 4, 3, 2]);
    assert.equal((await call("audit/events?company_id=99", owner)).status, 422);
    assert.equal((await call("audit/events?company_id=2&branch_id=1", owner)).status, 422);
    assert.equal((await call("audit/events?cursor=invalid", owner)).status, 422);
    const csv = await (await call(selection + "&format=csv", owner)).text();
    assert.match(csv, /^timestamp_ist,actor,action,category,venture,branch,record,reference,outcome/);
    assert.equal(csv.split("\r\n").length, 4);
    assert(csv.includes(`"'=SUM(1,2)"`));
    assert(!csv.includes("must-never-export"));
    const options = await (await call("audit/options", owner)).json();
    assert.deepEqual(options.companies.map((r: { id: number }) => r.id).sort(), [1, 2]);
    assert(!JSON.stringify(options).includes("@example.test"));
    assert.equal(await collection.countDocuments(), 9);
  } finally {
    await disconnect();
    await mongo.stop();
  }
});
