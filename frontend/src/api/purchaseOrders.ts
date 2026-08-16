import { apiRequest } from "./client";
import type {
  PurchaseOrder,
  PurchaseOrderListItem,
  PurchaseOrderPayload,
  PurchaseOrderReceivePayload,
  PurchaseOrdersFromRecommendationsPayload,
  PurchaseOrderStatus,
} from "../types";

type PurchaseOrderListOptions = {
  branchId?: number;
  supplierId?: number;
  status?: PurchaseOrderStatus | "";
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

export function listPurchaseOrders(
  token: string,
  options: PurchaseOrderListOptions = {},
): Promise<PurchaseOrderListItem[]> {
  return apiRequest<PurchaseOrderListItem[]>(
    `/purchase-orders${queryString({
      branch_id: options.branchId,
      supplier_id: options.supplierId,
      status: options.status,
      search: options.search,
      limit: options.limit,
    })}`,
    {},
    token,
  );
}

export function getPurchaseOrder(token: string, id: number): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(`/purchase-orders/${id}`, {}, token);
}

export function createPurchaseOrder(token: string, payload: PurchaseOrderPayload): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(
    "/purchase-orders",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function updatePurchaseOrder(
  token: string,
  id: number,
  payload: PurchaseOrderPayload,
): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(
    `/purchase-orders/${id}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function submitPurchaseOrder(token: string, id: number): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(`/purchase-orders/${id}/submit`, { method: "POST" }, token);
}

export function approvePurchaseOrder(token: string, id: number): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(`/purchase-orders/${id}/approve`, { method: "POST" }, token);
}

export function cancelPurchaseOrder(token: string, id: number): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(`/purchase-orders/${id}/cancel`, { method: "POST" }, token);
}

export function markPurchaseOrderOrdered(token: string, id: number): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(`/purchase-orders/${id}/mark-ordered`, { method: "POST" }, token);
}

export function receivePurchaseOrder(
  token: string,
  id: number,
  payload: PurchaseOrderReceivePayload,
): Promise<PurchaseOrder> {
  return apiRequest<PurchaseOrder>(
    `/purchase-orders/${id}/receive`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function createPurchaseOrdersFromRecommendations(
  token: string,
  payload: PurchaseOrdersFromRecommendationsPayload,
): Promise<PurchaseOrder[]> {
  return apiRequest<PurchaseOrder[]>(
    "/purchase-orders/from-recommendations",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}
