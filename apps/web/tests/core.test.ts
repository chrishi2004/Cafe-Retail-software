import test from "node:test";
import assert from "node:assert/strict";
import {
  scaled,
  decimal,
  multiply,
  canonical,
  businessDate,
} from "../src/server/money";
import {
  hashPassword,
  verifyPassword,
  encrypt,
  decrypt,
  totp,
  verifiedTotpStep,
} from "../src/server/security";
import { databaseName } from "../src/server/db";
import { inBusinessRange } from "../src/businessDates";
import { dateBounds, invoiceInstant } from "../src/server/query";
import { cafeRange } from "../src/legacy/utils/cafeDates";
import { inputDateDaysAgo } from "../src/legacy/utils/format";
process.env.AUTH_SECRET = "unit-test-only-secret-with-at-least-32-characters";
test("money is exact in paise and rejects excessive precision", () => {
  assert.equal(scaled("10.25"), 1025);
  assert.equal(decimal(1025), "10.25");
  assert.equal(multiply(1025, 150), 1538);
  assert.equal(decimal(-25), "-0.25");
  for (const bad of ["1.001", "-1", "NaN", "1e4"])
    assert.throws(() => scaled(bad));
});
test("canonical request hash ignores object ordering but retains line order", () => {
  assert.equal(canonical({ a: 1, b: 2 }), canonical({ b: 2, a: 1 }));
  assert.notEqual(canonical([1, 2]), canonical([2, 1]));
});
test("business dates use Kolkata midnight for timestamps, presets and invoice input", () => {
  const boundary = new Date("2026-12-31T18:30:00Z");
  assert.equal(businessDate(new Date(boundary.getTime() - 1)), "2026-12-31");
  assert.equal(businessDate(boundary), "2027-01-01");
  assert.equal(businessDate("2027-01-01T00:00:00+05:30"), "2027-01-01");
  assert.equal(inputDateDaysAgo(0, boundary), "2027-01-01");
  assert.equal(inputDateDaysAgo(1, boundary), "2026-12-31");
  assert.deepEqual(cafeRange("Last Month", boundary), {
    startDate: "2026-12-01", endDate: "2026-12-31",
  });
  for (const value of ["2027-01-01", "2027-01-01T00:00", "2027-01-01T00:00:00+05:30"]) {
    assert.equal(invoiceInstant(value).toISOString(), boundary.toISOString());
  }
  assert.throws(() => invoiceInstant("2027-02-30"), /Invalid invoice date/);
  const onDay = (value: unknown) => inBusinessRange(value, "2027-01-01", "2027-01-01");
  assert.equal(onDay("2026-12-31T18:29:59.999Z"), false);
  assert.equal(onDay("2026-12-31T18:30:00.000Z"), true);
  assert.equal(onDay("2027-01-01T18:29:59.999Z"), true);
  assert.equal(onDay("2027-01-01T18:30:00.000Z"), false);
  assert.equal(onDay("2027-01-01"), true);
  assert.deepEqual(
    dateBounds(new URL("http://local/?end_date=2027-01-01"), "2027-01-02"),
    { start: null, end: "2027-01-01" },
  );
});
test("password derivation verifies only the correct password", async () => {
  const hash = await hashPassword("Test-password-123!");
  assert(await verifyPassword("Test-password-123!", hash));
  assert(!(await verifyPassword("Other-password-123!", hash)));
  assert(!hash.includes("Test-password"));
});
test("MFA encryption is authenticated and TOTP matches the RFC6238 vector", () => {
  const cipher = encrypt("JBSWY3DPEHPK3PXP");
  assert.equal(decrypt(cipher), "JBSWY3DPEHPK3PXP");
  const modified = Buffer.from(cipher, "base64");
  modified[15] ^= 1;
  assert.throws(() => decrypt(modified.toString("base64")));
  assert.equal(totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 1), "287082");
  assert.equal(verifiedTotpStep("JBSWY3DPEHPK3PXP", "123"), null);
});
test("web database selection cannot silently reuse a legacy name", () => {
  process.env.MONGODB_DB = "kalpvrik_cafe";
  assert.throws(databaseName);
  process.env.MONGODB_DB = "kalpvriksh_web_test_unit";
  assert.equal(databaseName(), "kalpvriksh_web_test_unit");
});

test('oversized mutation bodies are rejected before connecting to a database',async()=>{
 const {handle}=await import('../src/server/handler');
 const response=await handle(new Request('http://localhost/api/auth/login',{method:'POST',body:'x'.repeat(70000)}),['auth','login']);
 assert.equal(response.status,413);
});
