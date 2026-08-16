import { apiRequest } from "./client";

export type PreparationArea = "kitchen" | "beverage" | "counter" | "none";
export type TableSessionType = "dine_in" | "takeaway" | "counter";
export type TableSessionStatus = "open" | "bill_requested" | "billed" | "closed" | "cancelled";

export type MenuCategory = {
  id: number;
  public_id: string;
  company_id: number;
  branch_id: number | null;
  name: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MenuItem = {
  id: number;
  public_id: string;
  company_id: number;
  branch_id: number | null;
  category_id: number;
  product_id: number | null;
  name: string;
  description: string | null;
  image_reference: string | null;
  selling_price: string;
  preparation_area: PreparationArea;
  available: boolean;
  is_active: boolean;
  display_order: number;
  version: number;
  created_at: string;
  updated_at: string;
};

export type MenuCategoryInput = {
  branch_id: number | null;
  name: string;
  display_order: number;
  is_active: boolean;
};

export type MenuItemInput = {
  branch_id: number | null;
  category_id: number;
  product_id: number | null;
  name: string;
  description: string | null;
  image_reference: string | null;
  selling_price: string;
  preparation_area: PreparationArea;
  available: boolean;
  is_active: boolean;
  display_order: number;
};

export type CafeTable = {
  id: number;
  company_id: number;
  branch_id: number;
  table_code: string;
  display_name: string;
  capacity: number | null;
  area: string | null;
  is_active: boolean;
  version: number;
  active_session_public_id: string | null;
  active_session_status: TableSessionStatus | null;
  qr_active: boolean;
  qr_public_reference: string | null;
  created_at: string;
  updated_at: string;
};

export type CafeTableInput = {
  branch_id: number;
  table_code: string;
  display_name: string;
  capacity: number | null;
  area: string | null;
  is_active: boolean;
};

export type QRRotateResult = {
  table_code: string;
  table_display_name: string;
  public_reference: string;
  token_prefix: string;
  expires_at: string | null;
  qr_svg_data_uri: string | null;
  raw_token: string;
};

export type QRPrintData = {
  table_code: string;
  table_display_name: string;
  public_reference: string;
  token_prefix: string;
  expires_at: string | null;
  qr_svg_data_uri: string | null;
};

export type QRStatus = {
  public_reference: string;
  token_prefix: string;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  active: boolean;
  created_at: string;
};

export type TableSession = {
  id: number;
  public_id: string;
  company_id: number;
  branch_id: number;
  table_id: number;
  session_type: TableSessionType;
  status: TableSessionStatus;
  opened_by: number | null;
  opened_at: string;
  closed_by: number | null;
  closed_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export function listMenuCategories(token: string): Promise<MenuCategory[]> {
  return apiRequest<MenuCategory[]>("/cafe/menu/categories", {}, token);
}

export function createMenuCategory(token: string, payload: MenuCategoryInput): Promise<MenuCategory> {
  return apiRequest<MenuCategory>(
    "/cafe/menu/categories",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateMenuCategory(token: string, categoryId: number, payload: MenuCategoryInput): Promise<MenuCategory> {
  return apiRequest<MenuCategory>(
    `/cafe/menu/categories/${categoryId}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function listMenuItems(token: string, search = ""): Promise<MenuItem[]> {
  const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return apiRequest<MenuItem[]>(`/cafe/menu/items${query}`, {}, token);
}

export function createMenuItem(token: string, payload: MenuItemInput): Promise<MenuItem> {
  return apiRequest<MenuItem>(
    "/cafe/menu/items",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateMenuItem(token: string, itemId: number, payload: MenuItemInput & { expected_version: number }): Promise<MenuItem> {
  return apiRequest<MenuItem>(
    `/cafe/menu/items/${itemId}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function setMenuItemAvailability(token: string, itemId: number, available: boolean, expectedVersion: number): Promise<MenuItem> {
  return apiRequest<MenuItem>(
    `/cafe/menu/items/${itemId}/availability`,
    { method: "PATCH", body: JSON.stringify({ available, expected_version: expectedVersion }) },
    token,
  );
}

export function listCafeTables(token: string): Promise<CafeTable[]> {
  return apiRequest<CafeTable[]>("/cafe/tables", {}, token);
}

export function createCafeTable(token: string, payload: CafeTableInput): Promise<CafeTable> {
  return apiRequest<CafeTable>(
    "/cafe/tables",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export function updateCafeTable(token: string, tableId: number, payload: CafeTableInput & { expected_version: number }): Promise<CafeTable> {
  return apiRequest<CafeTable>(
    `/cafe/tables/${tableId}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export function deactivateCafeTable(token: string, tableId: number): Promise<CafeTable> {
  return apiRequest<CafeTable>(`/cafe/tables/${tableId}/deactivate`, { method: "POST" }, token);
}

export function rotateTableQr(token: string, tableId: number): Promise<QRRotateResult> {
  return apiRequest<QRRotateResult>(
    `/cafe/tables/${tableId}/qr/rotate`,
    { method: "POST", body: JSON.stringify({ expires_in_days: 365, public_base_url: "/order" }) },
    token,
  );
}

export function renderTableQr(token: string, tableId: number, rawToken: string): Promise<QRPrintData> {
  return apiRequest<QRPrintData>(
    `/cafe/tables/${tableId}/qr/render`,
    { method: "POST", body: JSON.stringify({ raw_token: rawToken, public_base_url: "/order" }) },
    token,
  );
}

export function getTableQrStatus(token: string, tableId: number): Promise<QRStatus | null> {
  return apiRequest<QRStatus | null>(`/cafe/tables/${tableId}/qr/status`, {}, token);
}

export function revokeTableQr(token: string, tableId: number): Promise<{ public_reference: string; revoked_at: string }> {
  return apiRequest(`/cafe/tables/${tableId}/qr/revoke`, { method: "POST" }, token);
}

export function openTableSession(token: string, tableId: number, sessionType: TableSessionType = "dine_in"): Promise<TableSession> {
  return apiRequest<TableSession>(
    "/cafe/table-sessions",
    { method: "POST", body: JSON.stringify({ table_id: tableId, session_type: sessionType }) },
    token,
  );
}

export function closeTableSession(token: string, publicId: string, version: number, cancel = false): Promise<TableSession> {
  return apiRequest<TableSession>(
    `/cafe/table-sessions/${publicId}/close`,
    { method: "POST", body: JSON.stringify({ expected_version: version, cancel }) },
    token,
  );
}

export function getTableSession(token: string, publicId: string): Promise<TableSession> {
  return apiRequest<TableSession>(`/cafe/table-sessions/${publicId}`, {}, token);
}