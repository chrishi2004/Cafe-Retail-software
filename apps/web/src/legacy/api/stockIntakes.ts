import { apiRequest } from "./client";

export type StockIntakeLine = {
  id: number;
  product_id: number;
  product_name: string;
  product_sku: string;
  unit_of_measure: string;
  quantity: string;
  unit_cost: string;
  line_total: string;
};

export type StockIntake = {
  id: number;
  company_id: number;
  branch_id: number;
  branch_name: string;
  purchase_date: string;
  supplier_id: number | null;
  supplier_name: string | null;
  vendor_name: string | null;
  reference_number: string | null;
  payment_mode: string;
  notes: string | null;
  items: StockIntakeLine[];
  item_count: number;
  total_amount: string;
  status: string;
  expense_id: number | null;
  created_by: number;
  created_by_name: string;
  created_at: string;
  updated_at: string;
};

export type StockIntakePayload = {
  branch_id: number;
  supplier_id?: number | null;
  purchase_date: string;
  vendor_name?: string | null;
  reference_number?: string | null;
  payment_mode: string;
  record_expense: boolean;
  notes?: string | null;
  items: Array<{ product_id: number; quantity: string; unit_cost: string }>;
};

export function listStockIntakes(
  token: string,
  options: { branchId?: number; startDate?: string; endDate?: string } = {},
) {
  const params = new URLSearchParams();
  if (options.branchId) params.set("branch_id", String(options.branchId));
  if (options.startDate) params.set("start_date", options.startDate);
  if (options.endDate) params.set("end_date", options.endDate);
  const query = params.toString();
  return apiRequest<StockIntake[]>(
    `/cafe/stock-intakes${query ? `?${query}` : ""}`,
    {},
    token,
  );
}

export function createStockIntake(
  token: string,
  payload: StockIntakePayload,
  idempotencyKey: string,
) {
  return apiRequest<StockIntake>(
    "/cafe/stock-intakes",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    },
    token,
  );
}
