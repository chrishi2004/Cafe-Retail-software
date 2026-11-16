import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import test from "node:test";
import { chromium } from "@playwright/test";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { disconnect } from "../src/server/db";
import { totp } from "../src/server/security";

test("owner creates an employee, who sets a private password and can be deactivated", { timeout: 90000 }, async () => {
  const mongo = await MongoMemoryReplSet.create({
    instanceOpts: [{ args: ["--nounixsocket"] }],
    replSet: { count: 1, storageEngine: "wiredTiger" },
  });
  const origin = "http://127.0.0.1:4318";
  const ownerPassword = "Browser-owner-password-123!";
  const staffPassword = "Browser-employee-password-123!";
  const staffEmail = "new-staff@example.test";
  Object.assign(process.env, {
    MONGODB_URI: mongo.getUri(),
    MONGODB_DB: "kalpvriksh_web_test_staff_browser",
    AUTH_SECRET: "staff-browser-only-secret-with-at-least-32-characters",
    BOOTSTRAP_OWNER_EMAIL: "owner@example.test",
    BOOTSTRAP_OWNER_PASSWORD: ownerPassword,
    BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@example.test",
    BOOTSTRAP_CAFE_CASHIER_PASSWORD: staffPassword,
    BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@example.test",
    BOOTSTRAP_RETAIL_CASHIER_PASSWORD: staffPassword,
  });
  let server: ReturnType<typeof spawn> | undefined;
  let browser: Awaited<ReturnType<typeof chromium.launch>> | undefined;
  let log = "";
  try {
    const enrolled = await bootstrap();
    server = spawn(process.execPath,
      [resolve("node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", "4318"],
      { env: { ...process.env, NODE_ENV: "production" }, stdio: ["ignore", "pipe", "pipe"] });
    server.stdout?.on("data", (chunk) => { log += String(chunk); });
    server.stderr?.on("data", (chunk) => { log += String(chunk); });
    let ready = false;
    for (let i = 0; i < 80; i++) {
      try { if ((await fetch(`${origin}/api/health`)).ok) { ready = true; break; } } catch {}
      await new Promise((done) => setTimeout(done, 100));
    }
    assert(ready, log);
    browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
    const owner = await browser.newPage();
    const staff = await browser.newPage();
    const errors: string[] = [];
    owner.on("pageerror", (error) => { errors.push(error.message); });
    staff.on("pageerror", (error) => { errors.push(error.message); });

    await owner.goto(`${origin}/login`);
    await owner.getByLabel("Email", { exact: true }).fill("owner@example.test");
    await owner.getByLabel("Password", { exact: true }).fill(ownerPassword);
    await owner.getByLabel("Authenticator code", { exact: true }).fill(totp(enrolled.totpSecret));
    await owner.getByRole("button", { name: "Sign in", exact: true }).click();
    await owner.waitForURL("**/super-admin/ventures");
    await owner.getByRole("button", { name: "Users", exact: true }).click();
    await owner.getByRole("button", { name: "Add employee", exact: true }).click();
    await owner.getByLabel("Full name").fill("Browser Employee");
    await owner.getByLabel("Email", { exact: true }).fill(staffEmail);
    await owner.getByLabel("Venture", { exact: true }).selectOption("1");
    await owner.getByLabel("Assigned branch", { exact: true }).selectOption("1");
    await owner.getByRole("button", { name: "Save employee", exact: true }).click();
    await owner.getByLabel("Your password", { exact: true }).fill(ownerPassword);
    await owner.getByLabel("Authenticator code", { exact: true }).fill(totp(enrolled.totpSecret));
    await owner.getByRole("button", { name: "Verify and continue", exact: true }).click();
    await owner.getByText("Employee added.", { exact: true }).waitFor();
    const setupLink = await owner.getByLabel("Setup link", { exact: true }).inputValue();
    assert.equal(new URL(setupLink).pathname, "/account/setup");
    const row = owner.getByRole("row").filter({ hasText: staffEmail });
    await row.getByText("Setup required", { exact: true }).waitFor();

    await staff.goto(setupLink);
    await staff.getByLabel("New password", { exact: true }).fill(staffPassword);
    await staff.getByLabel("Confirm new password", { exact: true }).fill(staffPassword);
    await staff.getByRole("button", { name: "Set password", exact: true }).click();
    await staff.getByText(/Password saved/).waitFor();
    assert.equal(new URL(staff.url()).hash, "");
    await staff.getByRole("link", { name: "Back to sign in", exact: true }).click();
    await staff.getByLabel("Email", { exact: true }).fill(staffEmail);
    await staff.getByLabel("Password", { exact: true }).fill(staffPassword);
    await staff.getByRole("button", { name: "Sign in", exact: true }).click();
    await staff.waitForURL("**/cafe/pos");
    await staff.getByRole("link", { name: "Account security", exact: true }).click();
    await staff.getByRole("button", { name: "Enable authenticator", exact: true }).waitFor();
    await staff.goto(`${origin}/super-admin/audit`);
    await staff.waitForURL("**/cafe/pos");
    await staff.goto(`${origin}/cafe/users`);
    await staff.waitForURL("**/cafe/pos");

    await owner.reload();
    await owner.getByLabel("Search employees", { exact: true }).fill(staffEmail);
    await row.getByText("Active", { exact: true }).waitFor();
    assert.match(await row.innerText(), /IST/);
    await row.getByRole("button", { name: "Edit", exact: true }).click();
    await owner.getByLabel("Full name", { exact: true }).fill("Renamed Employee");
    await owner.getByRole("button", { name: "Save employee", exact: true }).click();
    await row.getByText("Renamed Employee", { exact: true }).waitFor();
    owner.once("dialog", (dialog) => void dialog.accept());
    await row.getByRole("button", { name: "Deactivate", exact: true }).click();
    await row.getByText("Inactive", { exact: true }).waitFor();
    await owner.getByRole("button", { name: "Activity & Audit", exact: true }).click();
    await owner.getByRole("heading", { name: "Activity & Audit", exact: true }).waitFor();
    const deactivation = owner.getByRole("row").filter({ hasText: "Employee deactivated" });
    await deactivation.waitFor();
    assert.match(await deactivation.innerText(), /IST/);
    await owner.getByLabel("Category", { exact: true }).selectOption("employees");
    await owner.getByRole("button", { name: "Apply filters", exact: true }).click();
    await deactivation.waitFor();
    const auditDownload = owner.waitForEvent("download");
    await owner.getByRole("button", { name: "Download CSV", exact: true }).click();
    assert.match((await auditDownload).suggestedFilename(), /^operational-audit-.*\.csv$/);

    await staff.reload();
    await staff.getByRole("button", { name: "Sign in", exact: true }).waitFor();
    assert.deepEqual(errors, []);
  } finally {
    await browser?.close();
    if (server && server.exitCode === null && server.signalCode === null) {
      const child = server;
      await new Promise<void>((done) => { child.once("exit", () => done()); child.kill("SIGTERM"); });
    }
    await disconnect();
    await mongo.stop();
  }
});
