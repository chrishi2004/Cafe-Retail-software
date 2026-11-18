import assert from "node:assert/strict";
import test from "node:test";
import { allocateLots, receiveLots } from "../src/server/lots";

test("allocation excludes expired lots, preserves unallocated stock and transfers lot identity", () => {
  const expired = { batch_number: "old", expiry_date: "2000-01-01", quantity_scaled: 200 };
  const first = { batch_number: "first", expiry_date: "2098-01-01", quantity_scaled: 300 };
  const later = { batch_number: "later", expiry_date: "2099-01-01", quantity_scaled: 400 };
  const lots = [later, expired, first];
  const sale = allocateLots(lots, 1000, 450, true, true, true);
  assert.deepEqual(sale.allocated, [first, { ...later, quantity_scaled: 150 }]);
  assert.throws(() => allocateLots(lots, 1000, 750, true, true, true));
  assert.throws(() => allocateLots([], 100, 1, true, true, true));
  assert.equal(allocateLots([], 100, 100, true).allocated.length, 0);
  assert.deepEqual(receiveLots([later], sale.allocated), [{ ...later, quantity_scaled: 550 }, first]);
  assert.deepEqual(allocateLots(lots, 1000, 100, false).allocated, [{ ...expired, quantity_scaled: 100 }]);
});
