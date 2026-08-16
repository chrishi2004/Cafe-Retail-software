import { apiRequest } from "./client";
import type {
  Branch,
  BranchPayload,
  Category,
  CategoryPayload,
  Product,
  ProductPayload,
  Supplier,
  SupplierPayload,
} from "../types";

type ListOptions = {
  search?: string;
  includeInactive?: boolean;
};

type ProductListOptions = ListOptions & {
  categoryId?: number;
  supplierId?: number;
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

export function listProducts(token: string, options: ProductListOptions = {}): Promise<Product[]> {
  return apiRequest<Product[]>(
    `/products${queryString({
      search: options.search,
      include_inactive: options.includeInactive,
      category_id: options.categoryId,
      supplier_id: options.supplierId,
    })}`,
    {},
    token,
  );
}

export function searchProducts(token: string, query: string, includeInactive = false): Promise<Product[]> {
  return apiRequest<Product[]>(
    `/products/search${queryString({ q: query, include_inactive: includeInactive })}`,
    {},
    token,
  );
}

export function createProduct(token: string, payload: ProductPayload): Promise<Product> {
  return apiRequest<Product>(
    "/products",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateProduct(token: string, id: number, payload: ProductPayload): Promise<Product> {
  return apiRequest<Product>(
    `/products/${id}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function deactivateProduct(token: string, id: number): Promise<Product> {
  return apiRequest<Product>(`/products/${id}/deactivate`, { method: "PATCH" }, token);
}

export function listCategories(token: string, search?: string): Promise<Category[]> {
  return apiRequest<Category[]>(`/categories${queryString({ search })}`, {}, token);
}

export function createCategory(token: string, payload: CategoryPayload): Promise<Category> {
  return apiRequest<Category>(
    "/categories",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateCategory(token: string, id: number, payload: CategoryPayload): Promise<Category> {
  return apiRequest<Category>(
    `/categories/${id}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function listSuppliers(token: string, options: ListOptions = {}): Promise<Supplier[]> {
  return apiRequest<Supplier[]>(
    `/suppliers${queryString({
      search: options.search,
      include_inactive: options.includeInactive,
    })}`,
    {},
    token,
  );
}

export function createSupplier(token: string, payload: SupplierPayload): Promise<Supplier> {
  return apiRequest<Supplier>(
    "/suppliers",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateSupplier(token: string, id: number, payload: SupplierPayload): Promise<Supplier> {
  return apiRequest<Supplier>(
    `/suppliers/${id}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function listBranches(token: string, options: ListOptions = {}): Promise<Branch[]> {
  return apiRequest<Branch[]>(
    `/branches${queryString({
      search: options.search,
      include_inactive: options.includeInactive,
    })}`,
    {},
    token,
  );
}

export function createBranch(token: string, payload: BranchPayload): Promise<Branch> {
  return apiRequest<Branch>(
    "/branches",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateBranch(token: string, id: number, payload: BranchPayload): Promise<Branch> {
  return apiRequest<Branch>(
    `/branches/${id}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}
