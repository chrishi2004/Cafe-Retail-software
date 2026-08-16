import { apiRequest } from "./client";
import type {
  BusinessProfile,
  BusinessProfilePayload,
  InvoiceSequence,
  InvoiceSequencePayload,
  PaymentMode,
  PaymentModePayload,
  TaxRate,
  TaxRatePayload,
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

export function getBusinessProfile(token: string): Promise<BusinessProfile> {
  return apiRequest<BusinessProfile>("/business-profile", {}, token);
}

export function updateBusinessProfile(token: string, payload: BusinessProfilePayload): Promise<BusinessProfile> {
  return apiRequest<BusinessProfile>(
    "/business-profile",
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function listTaxRates(token: string, includeInactive = false): Promise<TaxRate[]> {
  return apiRequest<TaxRate[]>(`/tax-rates${queryString({ include_inactive: includeInactive })}`, {}, token);
}

export function createTaxRate(token: string, payload: TaxRatePayload): Promise<TaxRate> {
  return apiRequest<TaxRate>("/tax-rates", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function updateTaxRate(token: string, id: number, payload: TaxRatePayload): Promise<TaxRate> {
  return apiRequest<TaxRate>(`/tax-rates/${id}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export function listPaymentModes(token: string, includeInactive = false): Promise<PaymentMode[]> {
  return apiRequest<PaymentMode[]>(`/payment-modes${queryString({ include_inactive: includeInactive })}`, {}, token);
}

export function createPaymentMode(token: string, payload: PaymentModePayload): Promise<PaymentMode> {
  return apiRequest<PaymentMode>("/payment-modes", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function updatePaymentMode(token: string, id: number, payload: PaymentModePayload): Promise<PaymentMode> {
  return apiRequest<PaymentMode>(`/payment-modes/${id}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export function listInvoiceSequences(token: string, includeInactive = false): Promise<InvoiceSequence[]> {
  return apiRequest<InvoiceSequence[]>(
    `/invoice-sequences${queryString({ include_inactive: includeInactive })}`,
    {},
    token,
  );
}

export function createInvoiceSequence(token: string, payload: InvoiceSequencePayload): Promise<InvoiceSequence> {
  return apiRequest<InvoiceSequence>(
    "/invoice-sequences",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateInvoiceSequence(
  token: string,
  id: number,
  payload: InvoiceSequencePayload,
): Promise<InvoiceSequence> {
  return apiRequest<InvoiceSequence>(
    `/invoice-sequences/${id}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

