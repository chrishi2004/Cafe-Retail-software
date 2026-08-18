import { PublicCafeApiError, type PublicOrderInput } from "./publicCafeClient";

export const CLOUD_API_BASE_URL =
  import.meta.env.VITE_CLOUD_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export const OPERATIONAL_API_BASE_URL =
  import.meta.env.VITE_OPERATIONAL_API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export type CloudQrResolution = {
  publication_id: string;
  table_code: string;
  table_display_name: string;
  snapshot_at: string;
  stale_age_seconds: number;
  ordering_enabled: boolean;
};

export type CloudSafeMenu = {
  publication_id: string;
  version: number;
  snapshot_at: string;
  stale_age_seconds: number;
  categories: Array<{
    source_category_id: string;
    name: string;
    display_order: number;
  }>;
  items: Array<{
    source_menu_item_id: string;
    source_category_id: string;
    name: string;
    description: string | null;
    image_reference: string | null;
    selling_price: string;
    preparation_area: string;
    available: boolean;
    display_order: number;
  }>;
};

export type CloudOrder = {
  public_id: string;
  status: string;
  estimated_total: string;
  created_at: string;
  items: Array<{
    menu_item_public_id: string;
    name: string;
    quantity: number;
    unit_price: string;
    line_total: string;
  }>;
  replayed: boolean;
};

async function cloudRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${CLOUD_API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    let payload: { error?: { code?: string; message?: string } } = {};
    try {
      payload = (await response.json()) as typeof payload;
    } catch {
      // Cloud errors deliberately fall back to a generic message.
    }
    throw new PublicCafeApiError(
      response.status,
      payload.error?.code ?? "cloud_request_failed",
      payload.error?.message ?? "The cloud continuity service is unavailable.",
    );
  }
  return (await response.json()) as T;
}

export function resolveCloudQr(opaqueToken: string): Promise<CloudQrResolution> {
  return cloudRequest<CloudQrResolution>("/cloud/public/cafe/qr/resolve", {
    method: "POST",
    body: JSON.stringify({ opaque_token: opaqueToken }),
  });
}

export function getCloudSafeMenu(publicationId: string): Promise<CloudSafeMenu> {
  return cloudRequest<CloudSafeMenu>(`/cloud/public/cafe/menu/${encodeURIComponent(publicationId)}`);
}

export function submitCloudOrder(
  publicationId: string,
  opaqueQr: string,
  idempotencyKey: string,
  payload: PublicOrderInput,
): Promise<CloudOrder> {
  return cloudRequest<CloudOrder>("/cloud/public/cafe/orders", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({
      publication_id: publicationId,
      opaque_qr: opaqueQr,
      items: payload.items,
      customer_notes: payload.customer_notes,
    }),
  });
}

export function getCloudOrder(publicId: string): Promise<CloudOrder> {
  return cloudRequest<CloudOrder>(`/cloud/public/cafe/orders/${encodeURIComponent(publicId)}`);
}
