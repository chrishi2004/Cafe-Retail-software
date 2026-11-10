import { apiRequest } from "./client";

export type ExpenseCategory =
  | "maintenance"
  | "utilities"
  | "rent"
  | "wages"
  | "cleaning"
  | "repairs"
  | "transport"
  | "marketing"
  | "licenses"
  | "stock_purchase"
  | "miscellaneous";

export type Expense = {
  id: number;
  company_id: number;
  branch_id: number;
  branch_name: string;
  expense_date: string;
  category: ExpenseCategory;
  description: string;
  amount: string;
  payment_mode: string;
  vendor_name: string | null;
  reference_number: string | null;
  notes: string | null;
  status: "posted" | "voided";
  source_type: "manual" | "stock_intake" | string;
  source_id: number | null;
  created_by: number;
  created_by_name: string;
  voided_by: number | null;
  voided_by_name: string | null;
  voided_at: string | null;
  void_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type ExpenseSummary = {
  total_expenses: string;
  cash_expenses: string;
  non_cash_expenses: string;
  stock_purchase_expenses: string;
  expense_count: number;
  by_category: Record<string, string>;
};

export type ExpensePayload = {
  branch_id: number;
  expense_date: string;
  category: ExpenseCategory;
  description: string;
  amount: string;
  payment_mode: string;
  vendor_name?: string | null;
  reference_number?: string | null;
  notes?: string | null;
};

export type ExpenseFilters = {
  branchId?: number;
  startDate?: string;
  endDate?: string;
  category?: string;
  paymentMode?: string;
  status?: string;
};

function query(filters: ExpenseFilters) {
  const params = new URLSearchParams();
  if (filters.branchId) params.set("branch_id", String(filters.branchId));
  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  if (filters.category) params.set("category", filters.category);
  if (filters.paymentMode) params.set("payment_mode", filters.paymentMode);
  if (filters.status) params.set("status", filters.status);
  const value = params.toString();
  return value ? `?${value}` : "";
}

export function listExpenses(token: string, filters: ExpenseFilters = {}) {
  return apiRequest<Expense[]>(`/expenses${query(filters)}`, {}, token);
}

export function getExpenseSummary(token: string, filters: ExpenseFilters = {}) {
  return apiRequest<ExpenseSummary>(`/expenses/summary${query(filters)}`, {}, token);
}

export function createExpense(token: string, payload: ExpensePayload) {
  return apiRequest<Expense>(
    "/expenses",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function voidExpense(token: string, id: number, reason: string) {
  return apiRequest<Expense>(
    `/expenses/${id}/void`,
    { method: "POST", body: JSON.stringify({ reason }) },
    token,
  );
}
