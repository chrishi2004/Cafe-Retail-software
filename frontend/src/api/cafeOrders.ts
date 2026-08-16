import { apiRequest } from "./client";
import type { PreparationArea, TableSessionStatus, TableSessionType } from "./cafe";

export type CafeOrderStatus =
  | "placed"
  | "accepted"
  | "preparing"
  | "ready"
  | "served"
  | "bill_requested"
  | "billed"
  | "closed"
  | "rejected"
  | "cancelled";

export type CafeOrderSource = "qr_customer" | "order_taker" | "billing_counter" | "manager";

export type CafeOrderItem = {
  menu_item_public_id: string;
  name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  status: string;
  preparation_area: PreparationArea;
  notes: string | null;
};

export type CafeOrder = {
  public_id: string;
  order_number: string;
  order_type: TableSessionType;
  source_channel: CafeOrderSource;
  status: CafeOrderStatus;
  branch_id: number;
  table_session_public_id: string | null;
  table_code: string | null;
  subtotal: string;
  discount_total: string;
  estimated_total: string;
  customer_notes: string | null;
  created_by: number | null;
  accepted_by: number | null;
  version: number;
  placed_at: string;
  accepted_at: string | null;
  served_at: string | null;
  cancelled_at: string | null;
  items: CafeOrderItem[];
};

export type KitchenOrder = {
  public_id: string;
  order_number: string;
  table_reference: string | null;
  source_channel: CafeOrderSource;
  status: CafeOrderStatus;
  age_seconds: number;
  version: number;
  items: Array<{
    name: string;
    quantity: number;
    status: string;
    preparation_area: PreparationArea;
    notes: string | null;
  }>;
};

export type StaffOrderInput = {
  order_type: TableSessionType;
  branch_id?: number;
  table_session_public_id?: string;
  customer_notes?: string;
  items: Array<{ menu_item_public_id: string; quantity: number; notes?: string }>;
};

export type OrderFilters = {
  branchId?: number;
  tableId?: number;
  status?: CafeOrderStatus;
  source?: CafeOrderSource;
  preparationArea?: PreparationArea;
  businessDate?: string;
  unbilledOnly?: boolean;
};

export type TableSessionBillRequest = {
  public_id: string;
  status: TableSessionStatus;
  bill_requested_at: string;
  version: number;
  affected_order_public_ids: string[];
};

export function listCafeOrders(token: string, filters: OrderFilters = {}): Promise<CafeOrder[]> {
  const params = new URLSearchParams();
  if (filters.branchId) params.set("branch_id", String(filters.branchId));
  if (filters.tableId) params.set("table_id", String(filters.tableId));
  if (filters.status) params.set("status", filters.status);
  if (filters.source) params.set("source", filters.source);
  if (filters.preparationArea) params.set("preparation_area", filters.preparationArea);
  if (filters.businessDate) params.set("business_date", filters.businessDate);
  if (filters.unbilledOnly) params.set("unbilled_only", "true");
  const suffix = params.size ? `?${params.toString()}` : "";
  return apiRequest<CafeOrder[]>(`/cafe/orders${suffix}`, {}, token);
}

export function getCafeOrder(token: string, publicId: string): Promise<CafeOrder> {
  return apiRequest<CafeOrder>(`/cafe/orders/${publicId}`, {}, token);
}

export function createCafeStaffOrder(token: string, payload: StaffOrderInput): Promise<CafeOrder> {
  return apiRequest<CafeOrder>(
    "/cafe/orders",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function transitionCafeOrder(
  token: string,
  publicId: string,
  action: "accept" | "start-preparing" | "mark-ready" | "serve" | "request-bill",
  expectedVersion: number,
): Promise<CafeOrder> {
  return apiRequest<CafeOrder>(
    `/cafe/orders/${publicId}/${action}`,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) },
    token,
  );
}

export function reasonCafeOrder(
  token: string,
  publicId: string,
  action: "reject" | "cancel",
  expectedVersion: number,
  reason: string,
): Promise<CafeOrder> {
  return apiRequest<CafeOrder>(
    `/cafe/orders/${publicId}/${action}`,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion, reason }) },
    token,
  );
}

export function requestTableSessionBill(token: string, publicId: string, expectedVersion: number): Promise<TableSessionBillRequest> {
  return apiRequest<TableSessionBillRequest>(
    `/cafe/table-sessions/${publicId}/request-bill`,
    { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) },
    token,
  );
}

export function listKitchenOrders(
  token: string,
  preparationArea?: PreparationArea,
): Promise<KitchenOrder[]> {
  const suffix = preparationArea ? `?preparation_area=${encodeURIComponent(preparationArea)}` : "";
  return apiRequest<KitchenOrder[]>(`/cafe/kitchen/orders${suffix}`, {}, token);
}
