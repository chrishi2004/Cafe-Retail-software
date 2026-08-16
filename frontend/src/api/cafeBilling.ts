import { apiRequest } from "./client";

export type CafeBillItem = {
  order_public_id: string;
  order_number: string;
  source_channel: "qr_customer" | "order_taker" | "billing_counter" | "manager";
  order_status: string;
  order_item_id: number;
  menu_item_name: string;
  product_id: number | null;
  sku: string | null;
  quantity: number;
  unit_price: string;
  discount: string;
  line_total: string;
  billed: boolean;
  excluded_reason: string | null;
};

export type CafeBillQuote = {
  source_type: "cafe_table_session" | "cafe_takeaway";
  source_id: string;
  branch_id: number;
  table_session_public_id: string | null;
  table_session_status: string | null;
  source_version: number;
  subtotal: string;
  discount_total: string;
  taxable_total: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  round_off: string;
  grand_total: string;
  eligible_items: CafeBillItem[];
  excluded_items: CafeBillItem[];
};

export type CafeBillPaymentInput = {
  payment_mode_id?: number | null;
  amount: string;
  reference_number?: string | null;
  notes?: string | null;
};

export type CafeBillRequest = {
  expected_version: number;
  customer_id?: number | null;
  payments: CafeBillPaymentInput[];
};

export type CafeReceipt = {
  invoice_id: number;
  invoice_number: string;
  source_type: string;
  source_id: string;
  cafe_name: string;
  branch_name: string;
  invoice_type: string;
  invoice_status: string;
  payment_status: string;
  issued_at: string | null;
  subtotal: string;
  discount_total: string;
  taxable_total: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  round_off: string;
  grand_total: string;
  paid_amount: string;
  balance_due: string;
  gstin: null;
  items: Array<{
    name: string;
    sku: string;
    quantity: string;
    unit_price: string;
    discount: string;
    line_total: string;
  }>;
  payments: Array<{
    mode_name: string | null;
    amount: string;
    reference_number: string | null;
    is_credit_marker: boolean;
  }>;
};

export type CafeBillResult = {
  receipt: CafeReceipt;
  table_session_status: string | null;
  order_status: string | null;
  closed: boolean;
  idempotent_replay: boolean;
};

export function quoteCafeTableSession(token: string, publicId: string): Promise<CafeBillQuote> {
  return apiRequest<CafeBillQuote>(`/cafe/billing/table-sessions/${publicId}/quote`, {}, token);
}

export function quoteCafeOrder(token: string, publicId: string): Promise<CafeBillQuote> {
  return apiRequest<CafeBillQuote>(`/cafe/billing/orders/${publicId}/quote`, {}, token);
}

export function billCafeTableSession(
  token: string,
  publicId: string,
  payload: CafeBillRequest,
  idempotencyKey: string,
): Promise<CafeBillResult> {
  return apiRequest<CafeBillResult>(
    `/cafe/billing/table-sessions/${publicId}/bill`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function billCafeOrder(
  token: string,
  publicId: string,
  payload: CafeBillRequest,
  idempotencyKey: string,
): Promise<CafeBillResult> {
  return apiRequest<CafeBillResult>(
    `/cafe/billing/orders/${publicId}/bill`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function getCafeReceipt(token: string, invoiceId: number): Promise<CafeReceipt> {
  return apiRequest<CafeReceipt>(`/cafe/billing/invoices/${invoiceId}/receipt`, {}, token);
}

export function collectCafeInvoicePayment(
  token: string,
  invoiceId: number,
  payment: CafeBillPaymentInput,
): Promise<CafeBillResult> {
  return apiRequest<CafeBillResult>(
    `/cafe/billing/invoices/${invoiceId}/payments`,
    { method: "POST", body: JSON.stringify({ payment }) },
    token,
  );
}
