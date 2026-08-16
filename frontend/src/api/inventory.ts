import { apiRequest } from "./client";
import type {
  InventoryItem,
  ProductInventoryDetail,
  StockAdjustmentPayload,
  StockAdjustmentResponse,
  StockMovement,
  StockMovementType,
} from "../types";

type InventoryListOptions = {
  branchId?: number;
  categoryId?: number;
  supplierId?: number;
  search?: string;
  lowStock?: boolean;
};

type MovementListOptions = {
  productId?: number;
  branchId?: number;
  movementType?: StockMovementType;
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

export function listInventory(token: string, options: InventoryListOptions = {}): Promise<InventoryItem[]> {
  return apiRequest<InventoryItem[]>(
    `/inventory${queryString({
      branch_id: options.branchId,
      category_id: options.categoryId,
      supplier_id: options.supplierId,
      search: options.search,
      low_stock: options.lowStock,
    })}`,
    {},
    token,
  );
}

export function listLowStockInventory(
  token: string,
  options: Omit<InventoryListOptions, "lowStock"> = {},
): Promise<InventoryItem[]> {
  return apiRequest<InventoryItem[]>(
    `/inventory/low-stock${queryString({
      branch_id: options.branchId,
      category_id: options.categoryId,
      supplier_id: options.supplierId,
      search: options.search,
    })}`,
    {},
    token,
  );
}

export function getProductInventory(token: string, productId: number): Promise<ProductInventoryDetail> {
  return apiRequest<ProductInventoryDetail>(`/inventory/${productId}`, {}, token);
}

export function createStockAdjustment(
  token: string,
  payload: StockAdjustmentPayload,
): Promise<StockAdjustmentResponse> {
  return apiRequest<StockAdjustmentResponse>(
    "/inventory/adjustments",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function listStockMovements(
  token: string,
  options: MovementListOptions = {},
): Promise<StockMovement[]> {
  return apiRequest<StockMovement[]>(
    `/inventory/movements${queryString({
      product_id: options.productId,
      branch_id: options.branchId,
      movement_type: options.movementType,
      limit: options.limit,
    })}`,
    {},
    token,
  );
}
