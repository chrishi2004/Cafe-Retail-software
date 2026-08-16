import { apiRequest } from "./client";
import type {
  Invoice,
  InvoiceQuote,
  POSCheckoutPayload,
  POSProductSearchResult,
  POSQuotePayload,
} from "../types";

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

export function searchPosProducts(
  token: string,
  query: string,
  options: { branchId?: number; limit?: number } = {},
): Promise<POSProductSearchResult[]> {
  return apiRequest<POSProductSearchResult[]>(
    `/pos/products/search${queryString({ q: query, branch_id: options.branchId, limit: options.limit })}`,
    {},
    token,
  );
}

export function quotePosInvoice(token: string, payload: POSQuotePayload): Promise<InvoiceQuote> {
  return apiRequest<InvoiceQuote>("/pos/quote", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function checkoutPosInvoice(token: string, payload: POSCheckoutPayload): Promise<Invoice> {
  return apiRequest<Invoice>("/pos/checkout", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function holdDraftInvoice(token: string, payload: POSQuotePayload): Promise<Invoice> {
  return apiRequest<Invoice>("/invoices", { method: "POST", body: JSON.stringify(payload) }, token);
}
