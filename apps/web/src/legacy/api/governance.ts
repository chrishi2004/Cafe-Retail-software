import { apiRequest } from "./client";

export type Closing = {
  id: number; company_id: number; branch_id: number; business_date: string;
  opening_cash: string; cash_collections: string; cash_refunds: string; cash_expenses: string;
  expected_cash: string; counted_cash: string | null; variance: string | null;
  non_cash_refunds?: string; non_cash_total: string; non_cash_expenses: string; status: string; submitted_by: number | null; closed_by: number | null;
  reopened_by: number | null; reason: string | null; reopened_reason: string | null;
  created_at: string; updated_at: string;
};

export type PurgeRequest = {
  id: number; company_id: number; branch_id: number | null; entity_type: string; entity_id: number;
  reason: string; status: string; dependency_report: Record<string, unknown>;
  backup_reference: string | null; requested_by: number; approved_by: number | null;
  second_approved_by: number | null; executed_at: string | null; failure_reason: string | null;
};

export function createClosing(token: string, payload: { branch_id: number; business_date: string; opening_cash: string }) {
  return apiRequest<Closing>("/governance/closings", { method: "POST", body: JSON.stringify(payload) }, token);
}
export function submitClosing(token: string, id: number, counted_cash: string) {
  return apiRequest<Closing>(`/governance/closings/${id}/submit`, { method: "POST", body: JSON.stringify({ counted_cash }) }, token);
}
export function closeClosing(token: string, id: number) {
  return apiRequest<Closing>(`/governance/closings/${id}/close`, { method: "POST" }, token);
}
export function requestPurge(token: string, payload: { entity_type: string; entity_id: number; reason: string; backup_reference: string }) {
  return apiRequest<PurgeRequest>("/governance/purges", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function getClosing(token: string, branchId: number, businessDate: string) {
  return apiRequest<Closing | null>(`/governance/closings?branch_id=${branchId}&business_date=${businessDate}`, {}, token);
}

export function reopenClosing(token: string, id: number, reason: string) {
  return apiRequest<Closing>(`/governance/closings/${id}/reopen`, { method: "POST", body: JSON.stringify({ reason }) }, token);
}

export type RefundCase = {
  id: number;
  invoice_number: string;
  deleted_at: string;
  legacy: boolean;
  payments: Array<{
    id: number; mode: string; cash: boolean; received_date: string; amount: string;
    remaining: string; correction: string | null;
    refunds: Array<{ id: number; amount: string; date: string; reference: string | null }>;
  }>;
};

export function listRefunds(token: string, history: boolean, offset: number) {
  return apiRequest<{ items: RefundCase[]; has_more: boolean; page_size: number }>(
    `/governance/refunds?history=${history}&offset=${offset}`, {}, token,
  );
}

export function recordPaymentResolution(token: string, id: number, payment: number,
  payload: { action: "refund"; amount: string; refund_date: string; reference_number: string } |
           { action: "not_received"; reason: string }, key: string) {
  return apiRequest<{ refund_status: string; remaining: string }>(
    `/governance/refunds/${id}/payments/${payment}`,
    { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify({ ...payload, confirmed: true }) },
    token,
  );
}
