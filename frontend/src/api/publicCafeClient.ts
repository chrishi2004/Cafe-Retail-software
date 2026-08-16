export const PUBLIC_CAFE_API_BASE_URL =
  import.meta.env.VITE_OPERATIONAL_API_BASE_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000/api";

export type PublicQrResolution = {
  cafe_name: string;
  table_code: string;
  table_display_name: string;
  session_public_id: string;
  guest_access: string;
  guest_expires_at: string;
  ordering_enabled: boolean;
};

export type PublicMenuCategory = {
  public_id: string;
  name: string;
  display_order: number;
};

export type PublicMenuItem = {
  public_id: string;
  category_public_id: string;
  name: string;
  description: string | null;
  image_reference: string | null;
  selling_price: string;
  preparation_area: string;
  available: boolean;
  display_order: number;
};

export type PublicMenu = {
  cafe_name: string;
  table_code: string;
  table_display_name: string;
  session_public_id: string;
  session_status: string;
  categories: PublicMenuCategory[];
  items: PublicMenuItem[];
};

export type PublicOrderItemInput = {
  menu_item_public_id: string;
  quantity: number;
  notes?: string | null;
};

export type PublicOrderInput = {
  items: PublicOrderItemInput[];
  customer_notes?: string | null;
};

export type PublicOrderItem = {
  menu_item_public_id: string;
  name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  status: string;
  notes: string | null;
};

export type PublicOrder = {
  public_id: string;
  order_number: string;
  status: string;
  subtotal: string;
  discount_total: string;
  estimated_total: string;
  customer_notes: string | null;
  placed_at: string;
  items: PublicOrderItem[];
  replayed: boolean;
};

export type PublicSessionOrders = {
  cafe_name: string;
  table_code: string;
  table_display_name: string;
  session_public_id: string;
  session_status: string;
  orders: PublicOrder[];
};

export type PublicBillRequest = {
  session_public_id: string;
  session_status: string;
  bill_requested_at: string;
};

type ApiErrorShape = {
  error?: {
    code?: string;
    message?: string;
  };
};

export class PublicCafeApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  guestAccess?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (guestAccess) headers.set("X-Guest-Access", guestAccess);
  const response = await fetch(`${PUBLIC_CAFE_API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    let payload: ApiErrorShape = {};
    try {
      payload = (await response.json()) as ApiErrorShape;
    } catch {
      // Public errors deliberately fall back to a generic message.
    }
    throw new PublicCafeApiError(
      response.status,
      payload.error?.code ?? "request_failed",
      payload.error?.message ?? "This request could not be completed.",
    );
  }
  return (await response.json()) as T;
}

export function resolvePublicQr(qrToken: string): Promise<PublicQrResolution> {
  return request<PublicQrResolution>(`/public/cafe/qr/${encodeURIComponent(qrToken)}/resolve`, {
    method: "POST",
  });
}

export function getPublicMenu(sessionPublicId: string, guestAccess: string): Promise<PublicMenu> {
  return request<PublicMenu>(
    `/public/cafe/sessions/${encodeURIComponent(sessionPublicId)}/menu`,
    {},
    guestAccess,
  );
}

export function submitPublicOrder(
  sessionPublicId: string,
  guestAccess: string,
  idempotencyKey: string,
  payload: PublicOrderInput,
): Promise<PublicOrder> {
  return request<PublicOrder>(
    `/public/cafe/sessions/${encodeURIComponent(sessionPublicId)}/orders`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    },
    guestAccess,
  );
}

export function getPublicOrders(
  sessionPublicId: string,
  guestAccess: string,
): Promise<PublicSessionOrders> {
  return request<PublicSessionOrders>(
    `/public/cafe/sessions/${encodeURIComponent(sessionPublicId)}/orders`,
    {},
    guestAccess,
  );
}

export function requestPublicBill(
  sessionPublicId: string,
  guestAccess: string,
): Promise<PublicBillRequest> {
  return request<PublicBillRequest>(
    `/public/cafe/sessions/${encodeURIComponent(sessionPublicId)}/bill-request`,
    { method: "POST" },
    guestAccess,
  );
}
