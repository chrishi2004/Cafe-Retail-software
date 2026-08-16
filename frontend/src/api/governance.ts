import { apiRequest } from "./client";

export type Closing = {
  id: number; company_id: number; branch_id: number; business_date: string;
  opening_cash: string; cash_collections: string; cash_refunds: string; cash_expenses: string;
  expected_cash: string; counted_cash: string | null; variance: string | null;
  non_cash_total: string; status: string; submitted_by: number | null; closed_by: number | null;
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
