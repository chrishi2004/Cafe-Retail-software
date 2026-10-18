import { apiRequest } from "./client";
import type { ReorderPriority, ReorderRecommendation } from "../types";

export type ReorderRecommendationOptions = {
  branchId?: number;
  categoryId?: number;
  supplierId?: number;
  priority?: ReorderPriority;
  lookbackDays?: number;
  asOfDate?: string;
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

export function listReorderRecommendations(
  token: string,
  options: ReorderRecommendationOptions = {},
): Promise<ReorderRecommendation[]> {
  return apiRequest<ReorderRecommendation[]>(
    `/inventory/reorder-recommendations${queryString({
      branch_id: options.branchId,
      category_id: options.categoryId,
      supplier_id: options.supplierId,
      priority: options.priority,
      lookback_days: options.lookbackDays,
      as_of_date: options.asOfDate,
    })}`,
    {},
    token,
  );
}
