import { apiRequest } from "./client";

export type ReturnPayload = {
  reason: string;
  refund_mode: "customer_credit" | "cash" | "original_payment";
  idempotency_key: string;
  items: Array<{
    invoice_item_id: number;
    quantity: string;
    condition: "saleable" | "damaged";
    restock: boolean;
  }>;
};

export type SalesReturn = {
  id: number;
  return_number: string;
  invoice_id: number;
  total_amount: string;
  refund_mode: ReturnPayload["refund_mode"];
  status: string;
  credit_note: { credit_note_number: string; amount: string };
};

export function createSalesReturn(token: string, invoiceId: number, payload: ReturnPayload) {
  return apiRequest<SalesReturn>(`/returns/invoices/${invoiceId}`, { method: "POST", body: JSON.stringify(payload) }, token);
}
