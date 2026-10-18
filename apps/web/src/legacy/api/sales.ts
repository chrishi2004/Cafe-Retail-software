import { apiRequest } from "./client";
import type { Sale, SaleListItem, SalePayload, SalesSummary, SalesTrendPoint } from "../types";

type SalesListOptions = {
  branchId?: number;
  startDate?: string;
  endDate?: string;
  productId?: number;
  categoryId?: number;
  search?: string;
  limit?: number;
};

function queryString(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function salesQuery(options: SalesListOptions): string {
  return queryString({
    branch_id: options.branchId,
    start_date: options.startDate,
    end_date: options.endDate,
    product_id: options.productId,
    category_id: options.categoryId,
    search: options.search,
    limit: options.limit,
  });
}

export function listSales(token: string, options: SalesListOptions = {}): Promise<SaleListItem[]> {
  return apiRequest<SaleListItem[]>(`/sales${salesQuery(options)}`, {}, token);
}

export function createSale(token: string, payload: SalePayload): Promise<Sale> {
  return apiRequest<Sale>(
    "/sales",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function getSale(token: string, saleId: number): Promise<Sale> {
  return apiRequest<Sale>(`/sales/${saleId}`, {}, token);
}

export function getSalesSummary(token: string, options: SalesListOptions = {}): Promise<SalesSummary> {
  return apiRequest<SalesSummary>(`/sales/summary${salesQuery(options)}`, {}, token);
}

export function getSalesTrends(token: string, options: SalesListOptions = {}): Promise<SalesTrendPoint[]> {
  return apiRequest<SalesTrendPoint[]>(`/sales/trends${salesQuery(options)}`, {}, token);
}
