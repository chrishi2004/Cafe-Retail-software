import { apiRequest } from "./client";

export type PurchaseBill = { id: number; bill_number: string; total_amount: string; paid_amount: string; balance_due: string; status: string };

export function createPurchaseBill(token: string, payload: unknown) {
  return apiRequest<PurchaseBill>("/purchase-bills", { method: "POST", body: JSON.stringify(payload) }, token);
}
