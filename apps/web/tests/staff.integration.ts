import assert from "node:assert/strict";
import test from "node:test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { database, disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";
import { digest, totp } from "../src/server/security";

test("employee setup, branch and venture authority, MFA, and concurrent session revocation", { timeout: 120000 }, async () => {
  const server = await MongoMemoryReplSet.create({
    instanceOpts: [{ args: ["--nounixsocket"] }],
    replSet: { count: 1, storageEngine: "wiredTiger" },
  });
  const ownerPassword = "Owner-password-123!";
  const employeePassword = "Private-worker-123!";
  Object.assign(process.env, {
    MONGODB_URI: server.getUri(),
    MONGODB_DB: "kalpvriksh_web_test_staff",
    AUTH_SECRET: "staff-test-only-auth-secret-with-32-characters",
    BOOTSTRAP_OWNER_EMAIL: "owner@example.test",
    BOOTSTRAP_OWNER_PASSWORD: ownerPassword,
    BOOTSTRAP_CAFE_CASHIER_EMAIL: "counter@example.test",
    BOOTSTRAP_CAFE_CASHIER_PASSWORD: employeePassword,
    BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test",
    BOOTSTRAP_RETAIL_CASHIER_PASSWORD: employeePassword,
  });

  try {
    const setup = await bootstrap();
    const { db } = await database();
    await db.collection("branches").insertOne({ id: 3, company_id: 1, name: "Second Café branch", is_active: true });
    const call = async (route: string, method = "GET", body?: object, token?: string) => {
      const req = new Request(`http://localhost/api/${route}`, {
        method,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const result = await handle(req, route.split("/"));
      return { status: result.status, body: await result.json() };
    };
    const successful = async (...args: Parameters<typeof call>) => {
      const result = await call(...args);
      assert.equal(result.status, 200, `${args[1] ?? "GET"} ${args[0]}: ${JSON.stringify(result.body)}`);
      return result.body;
    };
    const signIn = (email: string, password = employeePassword, credential?: object) =>
      call("auth/login", "POST", { email, password, ...credential });
    const claim = (code: string, password = employeePassword) =>
      call("auth/employee-password", "POST", { code, password });
    const verify = (token: string, password: string, code?: string) =>
      successful("auth/step-up", "POST", { password, totp_code: code }, token);
    const add = (token: string, email: string, company_id: number, branch_id: number | null, role: string) =>
      successful("venture-users", "POST", { name: "Test employee", email, company_id, branch_id, role }, token);
    const patch = (id: number, token: string, values: object) => call(`venture-users/${id}`, "PUT", values, token);

    assert.equal((await signIn("owner@example.test", ownerPassword)).status, 401);
    const firstOwner = await signIn("owner@example.test", ownerPassword, { recovery_code: setup.recoveryCodes[0] });
    const secondOwner = await signIn("owner@example.test", ownerPassword, { recovery_code: setup.recoveryCodes[1] });
    assert.equal(firstOwner.status, 200);
    assert.equal(secondOwner.status, 200);
    const owner = firstOwner.body.access_token, owner2 = secondOwner.body.access_token;
    await verify(owner, ownerPassword, totp(setup.totpSecret));
    assert.equal((await call("venture-users", "POST", {}, owner2)).body.error.code, "step_up_required");
    await verify(owner2, ownerPassword, totp(setup.totpSecret));
    const labels = await successful("venture-users/options", "GET", undefined, owner);
    assert.equal(labels.ventures.length, 2);
    assert(labels.roles.includes("admin"));

    const manage = await add(owner, "manager@example.test", 1, 1, "store_manager");
    const admin = await add(owner, "admin@example.test", 1, 1, "staff");
    const worker = await add(owner, "worker@example.test", 1, 1, "staff");
    const otherBranch = await add(owner, "otherbranch@example.test", 1, 3, "kitchen");
    const otherVenture = await add(owner, "otherventure@example.test", 2, 2, "staff");
    assert.equal((await call("venture-users", "POST", {
      name: "Illegal admin", email: "new-admin@example.test", role: "admin", company_id: 1, branch_id: null,
    }, owner)).status, 422);
    assert.equal((await patch(firstOwner.body.user.id, owner, { is_active: false })).status, 403);
    const beforeClaim = (await successful("venture-users", "GET", undefined, owner))
      .find((row: { id: number }) => row.id === worker.id);
    assert.equal(beforeClaim.password_setup_required, true);
    assert.equal(beforeClaim.last_login_at, null);
    assert.equal(beforeClaim.setup, undefined);
    const pendingWorker = await db.collection("users").findOne({ id: worker.id });
    assert.equal(pendingWorker?.password_hash, undefined);
    assert.equal(pendingWorker?.password_setup_hash, digest(worker.setup.code));
    assert.equal((await signIn("worker@example.test")).status, 401);
    assert.deepEqual((await Promise.all([claim(worker.setup.code), claim(worker.setup.code)]))
      .map((result) => result.status).sort(), [200, 422]);
    for (const row of [manage, admin]) assert.equal((await claim(row.setup.code)).status, 200);
    const [w1, w2, w3] = await Promise.all([signIn(worker.email), signIn(worker.email), signIn(worker.email)]);
    for (const result of [w1, w2, w3]) assert.equal(result.status, 200);
    const tokens = [w1, w2, w3].map((result) => result.body.access_token);
    assert.equal(new Set(tokens).size, 3);
    await successful("auth/logout", "POST", {}, tokens[0]);
    assert.equal((await call("auth/me", "GET", undefined, tokens[0])).status, 401);
    for (const token of tokens.slice(1)) await successful("auth/me", "GET", undefined, token);
    assert.equal((await call("venture-users", "GET", undefined, tokens[1])).status, 403);
    const directoryWorker = (await successful("venture-users", "GET", undefined, owner))
      .find((row: { id: number }) => row.id === worker.id);
    assert.equal(directoryWorker.password_setup_required, false);
    assert(Number.isFinite(Date.parse(directoryWorker.last_login_at)));

    const managerLogin = await signIn(manage.email);
    assert.equal(managerLogin.status, 200);
    const managerToken = managerLogin.body.access_token;
    await verify(managerToken, employeePassword);
    const managerRows = await successful("venture-users", "GET", undefined, managerToken);
    assert(managerRows.some((row: { id: number }) => row.id === worker.id));
    assert(!managerRows.some((row: { id: number }) => [otherBranch.id, otherVenture.id].includes(row.id)));
    assert.equal((await patch(otherBranch.id, managerToken, { is_active: false })).status, 404);
    assert.equal((await patch(worker.id, managerToken, { branch_id: 3 })).status, 422);
    assert.equal((await patch(worker.id, managerToken, { role: "store_manager" })).status, 422);
    assert.equal((await patch(worker.id, managerToken, { role: "admin", branch_id: null })).status, 422);
    assert.equal((await patch(worker.id, managerToken, { role: "super_admin" })).status, 422);
    assert.equal((await patch(worker.id, managerToken, { is_active: false })).status, 200);
    for (const token of tokens) assert.equal((await call("auth/me", "GET", undefined, token)).status, 401);
    assert.equal((await signIn(worker.email)).status, 401);
    assert.equal((await patch(worker.id, managerToken, { is_active: true })).status, 200);
    assert.equal((await signIn(worker.email)).status, 200);
    assert.equal((await call("auth/me", "GET", undefined, tokens[1])).status, 401);

    assert.equal((await patch(admin.id, owner, { role: "admin", branch_id: null })).status, 422);
    const enrolling = (await signIn(admin.email)).body.access_token;
    const enrollment = await successful("auth/mfa/enroll", "POST", {}, enrolling);
    await successful("auth/mfa/confirm", "POST", { totp_code: totp(enrollment.secret) }, enrolling);
    assert.equal((await call("auth/me", "GET", undefined, enrolling)).status, 401);
    assert.equal((await patch(admin.id, owner, { role: "admin", branch_id: null })).status, 200);
    assert.equal((await signIn(admin.email)).status, 401);
    const administrator = await signIn(admin.email, employeePassword, { recovery_code: enrollment.recovery_codes[0] });
    assert.equal(administrator.status, 200);
    const adminToken = administrator.body.access_token;
    await verify(adminToken, employeePassword, totp(enrollment.secret));
    assert.equal((await patch(otherVenture.id, adminToken, { is_active: false })).status, 404);
    assert.equal((await patch(otherBranch.id, adminToken, { company_id: 2, branch_id: 2, role: "staff" })).status, 422);
    assert.equal((await patch(worker.id, adminToken, { role: "admin", branch_id: null })).status, 422);
    assert.equal((await patch(otherBranch.id, adminToken, { name: "Updated Café worker" })).status, 200);
    await add(adminToken, "new-cafe-staff@example.test", 1, 3, "order_taker");

    const firstReset = await successful(`venture-users/${admin.id}/password-reset`, "POST", {}, owner);
    const secondReset = await successful(`venture-users/${admin.id}/password-reset`, "POST", {}, owner2);
    assert.equal((await claim(firstReset.setup.code)).status, 422);
    assert.equal((await call("auth/me", "GET", undefined, adminToken)).status, 401);
    assert.equal((await signIn(admin.email, employeePassword, { recovery_code: enrollment.recovery_codes[1] })).status, 401);
    const newPassword = "New-personal-password-789!";
    assert.equal((await claim(secondReset.setup.code, newPassword)).status, 200);
    assert.equal((await signIn(admin.email, newPassword)).status, 401);
    assert.equal((await signIn(admin.email, newPassword, { recovery_code: enrollment.recovery_codes[1] })).status, 200);
    await db.collection("users").updateOne({ id: otherVenture.id }, { $set: { password_setup_expires_at: new Date(2000, 0, 1) } });
    assert.equal((await claim(otherVenture.setup.code)).status, 422);
    assert.equal((await patch(otherBranch.id, owner, { is_active: false })).status, 200);
    assert.equal((await claim(otherBranch.setup.code)).status, 422);

    const events = await db.collection("audit_events").find({ entity_type: "user" }).toArray();
    for (const action of ["employee_create", "employee_update", "employee_deactivate", "employee_activate", "employee_role_change", "employee_password_reset", "employee_password_set"])
      assert(events.some((e) => e.action === action), action);
    assert(events.some((e) => e.action === "employee_deactivate" && e.entity_id === worker.id && e.actor_id === manage.id && e.company_id === 1 && e.branch_id === 1));
    assert(!JSON.stringify(events).includes(secondReset.setup.code));
    assert(!JSON.stringify(events).includes("password_hash"));
    await successful("auth/logout", "POST", {}, owner2);
    await successful("auth/me", "GET", undefined, owner);
    assert.equal((await call("auth/me", "GET", undefined, owner2)).status, 401);
  } finally {
    await disconnect();
    await server.stop();
  }
});
