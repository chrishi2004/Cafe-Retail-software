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
test("business day uses India midnight", () => {
  assert.equal(businessDate(new Date("2026-10-17T20:00:00Z")), "2026-10-18");
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
