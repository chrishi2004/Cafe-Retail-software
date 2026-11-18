import { apiRequest } from "./client";
import type {
  InventoryDashboard,
  OverviewDashboard,
  PurchaseOrdersDashboard,
  SalesDashboard,
} from "../types";

export type DashboardOptions = {
  branchId?: number;
  categoryId?: number;
  productId?: number;
  supplierId?: number;
  startDate?: string;
  endDate?: string;
};

function queryString(params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function dashboardQuery(options: DashboardOptions): string {
  return queryString({
    branch_id: options.branchId,
    category_id: options.categoryId,
    product_id: options.productId,
    supplier_id: options.supplierId,
    start_date: options.startDate,
    end_date: options.endDate,
  });
}

export function getOverviewDashboard(
  token: string,
  options: DashboardOptions = {},
): Promise<OverviewDashboard> {
  return apiRequest<OverviewDashboard>(`/dashboard/overview${dashboardQuery(options)}`, {}, token);
}

export function getSalesDashboard(token: string, options: DashboardOptions = {}): Promise<SalesDashboard> {
  return apiRequest<SalesDashboard>(`/dashboard/sales${dashboardQuery(options)}`, {}, token);
}

export function getInventoryDashboard(
  token: string,
  options: DashboardOptions = {},
): Promise<InventoryDashboard> {
  return apiRequest<InventoryDashboard>(`/dashboard/inventory${dashboardQuery(options)}`, {}, token);
}

export function getPurchaseOrdersDashboard(
  token: string,
  options: DashboardOptions = {},
): Promise<PurchaseOrdersDashboard> {
  return apiRequest<PurchaseOrdersDashboard>(`/dashboard/purchase-orders${dashboardQuery(options)}`, {}, token);
}
