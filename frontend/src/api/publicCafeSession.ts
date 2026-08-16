import {
  getPublicMenu,
  getPublicOrders,
  requestPublicBill,
  resolvePublicQr,
  submitPublicOrder,
  type PublicBillRequest,
  type PublicMenu,
  type PublicOrder,
  type PublicOrderInput,
  type PublicQrResolution,
  type PublicSessionOrders,
} from "./publicCafeClient";

export type PublicCafeIdentity = Pick<
  PublicQrResolution,
  "cafe_name" | "table_code" | "table_display_name" | "session_public_id" | "guest_expires_at"
>;

export type PublicCafeSession = {
  identity: PublicCafeIdentity;
  menu: () => Promise<PublicMenu>;
  orders: () => Promise<PublicSessionOrders>;
  submit: (retryKey: string, payload: PublicOrderInput) => Promise<PublicOrder>;
  requestBill: () => Promise<PublicBillRequest>;
};

export async function openPublicCafeSession(qrValue: string): Promise<PublicCafeSession> {
  const resolved = await resolvePublicQr(qrValue);
  const sessionId = resolved.session_public_id;
  const access = resolved.guest_access;
  return {
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
  return openPublicCafeSession(decodeURIComponent(path.slice(prefix.length)));
}
