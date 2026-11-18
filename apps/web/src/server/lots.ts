import { requireValue } from "./errors";
import { businessDate } from "./money";

export type Lot = { batch_number: string; expiry_date: string | null; quantity_scaled: number };

export function receiveLots(existing: Lot[] = [], incoming: Lot[]) {
  const lots = existing.map(lot => ({ ...lot }));
  for (const next of incoming) {
    const same = lots.find(lot => lot.batch_number === next.batch_number && lot.expiry_date === next.expiry_date);
    if (same) same.quantity_scaled += next.quantity_scaled;
    else lots.push({ ...next });
  }
  return lots;
}

export function allocateLots(existing: Lot[], onHand: number, quantity: number, sale: boolean, requireExpiry = false, requireBatch = false) {
  const lots = existing.map(lot => ({ ...lot })).sort((a, b) =>
    (a.expiry_date ?? "9999").localeCompare(b.expiry_date ?? "9999") || a.batch_number.localeCompare(b.batch_number));
  const unknown = onHand - lots.reduce((sum, lot) => sum + lot.quantity_scaled, 0);
  requireValue(unknown >= 0, "Lot balances exceed stock on hand. Reconcile inventory.");
  const today = businessDate();
  const allocated: Lot[] = [];
  let remaining = quantity;
  for (const lot of lots) {
    if (!remaining) break;
    if (sale && ((requireBatch && !lot.batch_number) || (requireExpiry && !lot.expiry_date) || (lot.expiry_date && lot.expiry_date < today))) continue;
    const take = Math.min(lot.quantity_scaled, remaining);
    allocated.push({ ...lot, quantity_scaled: take });
    lot.quantity_scaled -= take;
    remaining -= take;
  }
  requireValue(remaining === 0 || ((!sale || (!requireExpiry && !requireBatch)) && remaining <= unknown), "Insufficient eligible stock. Check batch numbers, expiry dates and available quantities.");
  return { lots: lots.filter(lot => lot.quantity_scaled > 0), allocated };
}
