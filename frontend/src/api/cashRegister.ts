import { apiRequest } from "./client";

export type RegisterMovement = {
  id: number;
  movement_type: "cash_in" | "cash_out" | "expense" | "adjustment";
  amount: string;
  reason: string;
  reference: string | null;
  recorded_by: number;
  occurred_at: string;
};

export type RegisterSummary = {
  id: number;
  company_id: number;
  branch_id: number;
  status: "open" | "closed";
  opening_float: string;
  opened_at: string;
  closed_at: string | null;
  expected_cash: string;
  counted_cash: string | null;
  variance: string | null;
  cash_collections: string;
  cash_refunds: string;
  cash_in: string;
  cash_out: string;
  expenses: string;
  non_cash_total: string;
  credit_total: string;
  mode_totals: { mode: string; amount: string }[];
  movements: RegisterMovement[];
};

export function openRegister(token: string, payload: { branch_id: number; opening_float: string }) {
  return apiRequest<RegisterSummary>("/cash-register/sessions", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function readRegister(token: string, id: number) {
  return apiRequest<RegisterSummary>(`/cash-register/sessions/${id}`, {}, token);
}

export function addRegisterMovement(token: string, id: number, payload: { movement_type: string; amount: string; reason: string; idempotency_key: string }) {
  return apiRequest<RegisterMovement>(`/cash-register/sessions/${id}/movements`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export function countRegister(token: string, id: number, counted_cash: string) {
  return apiRequest<RegisterSummary>(`/cash-register/sessions/${id}/count`, { method: "POST", body: JSON.stringify({ counted_cash }) }, token);
}

export function closeRegister(token: string, id: number) {
  return apiRequest<RegisterSummary>(`/cash-register/sessions/${id}/close`, { method: "POST" }, token);
}
