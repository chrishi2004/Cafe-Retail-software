import { apiRequest } from "./client";

export function createExpense(token: string, payload: unknown) {
  return apiRequest<{ id: number; amount: string }>("/expenses", { method: "POST", body: JSON.stringify(payload) }, token);
}
