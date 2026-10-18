import {
  PublicCafeApiError,
  getPublicMenu,
  getPublicOrders,
  requestPublicBill,
  resolvePublicQr,
  submitPublicOrder,
  type PublicBillRequest,
  type PublicMenu,
  type PublicOrder,
  type PublicOrderInput,
  type PublicSessionOrders,
} from "./publicCafeClient";
import {
  getCloudOrder,
  getCloudSafeMenu,
  requestCloudBill,
  resolveCloudQr,
  submitCloudOrder,
  type CloudOrder,
} from "./cloudClient";

export type PublicCafeIdentity = {
  cafe_name: string;
  table_code: string;
  table_display_name: string;
  session_public_id: string;
  guest_expires_at: string | null;
};

export type PublicCafeSession = {
  identity: PublicCafeIdentity;
  continuityMode: "local" | "cloud";
  menu: () => Promise<PublicMenu>;
  orders: () => Promise<PublicSessionOrders>;
  submit: (retryKey: string, payload: PublicOrderInput) => Promise<PublicOrder>;
  requestBill: () => Promise<PublicBillRequest>;
};

const CLOUD_ORDER_STORAGE_PREFIX = "kalpvrik:cloud-cafe-orders:";
const CLOUD_BILL_KEY_PREFIX = "kalpvrik:cloud-cafe-bill-key:";

function cloudOrderStorageKey(qrValue: string): string {
  return `${CLOUD_ORDER_STORAGE_PREFIX}${qrValue}`;
}

function cloudBillKeyStorageKey(qrValue: string, orderPublicId: string): string {
  return `${CLOUD_BILL_KEY_PREFIX}${qrValue}:${orderPublicId}`;
}

function readCloudOrderIds(qrValue: string): string[] {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(cloudOrderStorageKey(qrValue)) ?? "[]");
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string").slice(-20) : [];
  } catch {
    return [];
  }
}

function rememberCloudOrder(qrValue: string, publicId: string): void {
  const next = [...readCloudOrderIds(qrValue).filter((item) => item !== publicId), publicId].slice(-20);
  try {
    window.sessionStorage.setItem(cloudOrderStorageKey(qrValue), JSON.stringify(next));
  } catch {
    // Order status remains available for the current page even if storage is blocked.
  }
}

function cloudBillIdempotencyKey(qrValue: string, orderPublicId: string): string {
  const storageKey = cloudBillKeyStorageKey(qrValue, orderPublicId);
  try {
    const existing = window.sessionStorage.getItem(storageKey);
    if (existing && existing.length >= 8) return existing;
    const created = typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `bill-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.sessionStorage.setItem(storageKey, created);
    return created;
  } catch {
    return typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `bill-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

function toPublicCloudOrder(order: CloudOrder): PublicOrder {
  return {
    public_id: order.public_id,
    order_number: `CLOUD-${order.public_id.slice(0, 8).toUpperCase()}`,
    status: order.status,
    subtotal: order.estimated_total,
    discount_total: "0.00",
    estimated_total: order.estimated_total,
    customer_notes: null,
    placed_at: order.created_at,
    replayed: order.replayed,
    items: order.items.map((item) => ({
      menu_item_public_id: item.menu_item_public_id,
      name: item.name,
      quantity: item.quantity,
      unit_price: item.unit_price,
      line_total: item.line_total,
      status: order.status,
      notes: null,
    })),
  };
}

async function loadCloudOrders(qrValue: string): Promise<PublicOrder[]> {
  const results = await Promise.all(
    readCloudOrderIds(qrValue).map(async (publicId) => {
      try {
        return toPublicCloudOrder(await getCloudOrder(publicId));
      } catch {
        return null;
      }
    }),
  );
  return results.filter((order): order is PublicOrder => order !== null);
}

export async function openCloudCafeSession(qrValue: string): Promise<PublicCafeSession> {
  const resolved = await resolveCloudQr(qrValue);
  if (!resolved.ordering_enabled) {
    throw new PublicCafeApiError(409, "cloud_ordering_disabled", "Cloud Cafe ordering is not enabled for this publication.");
  }
  const sessionId = `cloud:${resolved.publication_id}:${resolved.table_code}`;
  const menu = async (): Promise<PublicMenu> => {
    const snapshot = await getCloudSafeMenu(resolved.publication_id);
    return {
      cafe_name: "Cafe",
      table_code: resolved.table_code,
      table_display_name: resolved.table_display_name,
      session_public_id: sessionId,
      session_status: "cloud_continuity",
      categories: snapshot.categories.map((category) => ({
        public_id: category.source_category_id,
        name: category.name,
        display_order: category.display_order,
      })),
      items: snapshot.items.map((item) => ({
        public_id: item.source_menu_item_id,
        category_public_id: item.source_category_id,
        name: item.name,
        description: item.description,
        image_reference: item.image_reference,
        selling_price: item.selling_price,
        preparation_area: item.preparation_area,
        available: item.available,
        display_order: item.display_order,
      })),
    };
  };
  return {
    continuityMode: "cloud",
    identity: {
      cafe_name: "Cafe",
      table_code: resolved.table_code,
      table_display_name: resolved.table_display_name,
      session_public_id: sessionId,
      guest_expires_at: null,
    },
    menu,
    orders: async () => ({
      cafe_name: "Cafe",
      table_code: resolved.table_code,
      table_display_name: resolved.table_display_name,
      session_public_id: sessionId,
      session_status: "cloud_continuity",
      orders: await loadCloudOrders(qrValue),
    }),
    submit: async (retryKey, payload) => {
      const order = await submitCloudOrder(resolved.publication_id, qrValue, retryKey, payload);
      rememberCloudOrder(qrValue, order.public_id);
      return toPublicCloudOrder(order);
    },
    requestBill: async () => {
      const ids = readCloudOrderIds(qrValue);
      const orderPublicId = ids.at(-1);
      if (!orderPublicId) {
        throw new PublicCafeApiError(409, "cloud_bill_requires_order", "Place an order before requesting the bill.");
      }
      const queued = await requestCloudBill(
        orderPublicId,
        resolved.publication_id,
        qrValue,
        cloudBillIdempotencyKey(qrValue, orderPublicId),
      );
      return {
        session_public_id: sessionId,
        session_status: "bill_requested",
        bill_requested_at: queued.bill_requested_at,
      };
    },
  };
}

// Retained only for local-network/PWA operation and regression coverage. The
// public hosted `/order/:qr-token` release path does not call this helper.
export async function openPublicCafeSession(qrValue: string): Promise<PublicCafeSession> {
  const resolved = await resolvePublicQr(qrValue);
  const sessionId = resolved.session_public_id;
  const access = resolved.guest_access;
  return {
    continuityMode: "local",
    identity: {
      cafe_name: resolved.cafe_name,
      table_code: resolved.table_code,
      table_display_name: resolved.table_display_name,
      session_public_id: resolved.session_public_id,
      guest_expires_at: resolved.guest_expires_at,
    },
    menu: () => getPublicMenu(sessionId, access),
    orders: () => getPublicOrders(sessionId, access),
    submit: (retryKey, payload) => submitPublicOrder(sessionId, access, retryKey, payload),
    requestBill: () => requestPublicBill(sessionId, access),
  };
}

export async function openCurrentPublicCafeSession(): Promise<PublicCafeSession> {
  const prefix = "/order/";
  const path = window.location.pathname;
  if (!path.startsWith(prefix) || path.length <= prefix.length) {
    throw new Error("Public Cafe route is not available.");
  }
  return openCloudCafeSession(decodeURIComponent(path.slice(prefix.length)));
}
