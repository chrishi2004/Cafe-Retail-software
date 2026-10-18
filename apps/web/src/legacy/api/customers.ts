import { apiRequest } from "./client";
import type {
  Customer,
  CustomerLedgerEntry,
  CustomerOutstanding,
  CustomerPayment,
  CustomerPaymentPayload,
  CustomerPayload,
} from "../types";

type CustomerListOptions = {
  search?: string;
  branchId?: number;
  includeInactive?: boolean;
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

export function listCustomers(token: string, options: CustomerListOptions = {}): Promise<Customer[]> {
  return apiRequest<Customer[]>(
    `/customers${queryString({
      search: options.search,
      branch_id: options.branchId,
      include_inactive: options.includeInactive,
      limit: options.limit,
    })}`,
    {},
    token,
  );
}

export function createCustomer(token: string, payload: CustomerPayload): Promise<Customer> {
  return apiRequest<Customer>("/customers", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function getCustomer(token: string, id: number): Promise<Customer> {
  return apiRequest<Customer>(`/customers/${id}`, {}, token);
}

export function updateCustomer(token: string, id: number, payload: CustomerPayload): Promise<Customer> {
  return apiRequest<Customer>(`/customers/${id}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export function deactivateCustomer(token: string, id: number): Promise<Customer> {
  return apiRequest<Customer>(`/customers/${id}/deactivate`, { method: "PATCH" }, token);
}

export function getCustomerLedger(token: string, id: number): Promise<CustomerLedgerEntry[]> {
  return apiRequest<CustomerLedgerEntry[]>(`/customers/${id}/ledger`, {}, token);
}

export function createCustomerPayment(
  token: string,
  id: number,
  payload: CustomerPaymentPayload,
): Promise<CustomerPayment> {
  return apiRequest<CustomerPayment>(
    `/customers/${id}/payments`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function listCustomerOutstanding(
  token: string,
  options: { branchId?: number; includeZero?: boolean } = {},
): Promise<CustomerOutstanding[]> {
  return apiRequest<CustomerOutstanding[]>(
    `/customer-ledger/outstanding${queryString({
      branch_id: options.branchId,
      include_zero: options.includeZero,
    })}`,
    {},
    token,
  );
}
