import { useCallback, useEffect, useMemo, useState } from "react";

import { getTableSession } from "../api/cafe";
import {
  listCafeOrders,
  reasonCafeOrder,
  requestTableSessionBill,
  transitionCafeOrder,
  type CafeOrder,
  type CafeOrderStatus,
} from "../api/cafeOrders";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

const ACTIVE: CafeOrderStatus[] = ["placed", "accepted", "preparing", "ready", "served", "bill_requested"];

function ageLabel(placedAt: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(placedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m`;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Cafe order operation failed.";
}

export function CafeLiveOrdersPage() {
  const { token, user } = useAuth();
  const [orders, setOrders] = useState<CafeOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | CafeOrderStatus>("all");
  const [sourceFilter, setSourceFilter] = useState("all");

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const rows = await listCafeOrders(token, { unbilledOnly: true });
      setOrders(rows);
      setError(null);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
    const poll = () => {
      if (document.visibilityState === "visible") void load();
    };
    const id = window.setInterval(poll, 5000);
    document.addEventListener("visibilitychange", poll);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [load]);

  const visible = useMemo(
    () => orders.filter((order) => {
      if (!ACTIVE.includes(order.status)) return false;
      if (statusFilter !== "all" && order.status !== statusFilter) return false;
      if (sourceFilter !== "all" && order.source_channel !== sourceFilter) return false;
      return true;
    }),
    [orders, sourceFilter, statusFilter],
  );

  const act = async (order: CafeOrder, action: "accept" | "start-preparing" | "mark-ready" | "serve") => {
    if (!token) return;
    try {
      await transitionCafeOrder(token, order.public_id, action, order.version);
      await load();
    } catch (actionError) {
      setError(errorMessage(actionError));
      await load();
    }
  };

  const requestBill = async (order: CafeOrder) => {
    if (!token) return;
    try {
      if (order.table_session_public_id) {
        const session = await getTableSession(token, order.table_session_public_id);
        await requestTableSessionBill(token, session.public_id, session.version);
      } else {
        await transitionCafeOrder(token, order.public_id, "request-bill", order.version);
      }
      await load();
    } catch (actionError) {
      setError(errorMessage(actionError));
      await load();
    }
  };

  const reasonAction = async (order: CafeOrder, action: "reject" | "cancel") => {
    if (!token) return;
    const reason = window.prompt(`${action === "reject" ? "Rejection" : "Cancellation"} reason`);
    if (!reason?.trim()) return;
    try {
      await reasonCafeOrder(token, order.public_id, action, order.version, reason.trim());
      await load();
    } catch (actionError) {
      setError(errorMessage(actionError));
      await load();
    }
  };

  if (loading) return <LoadingState label="Loading Cafe orders" />;

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Unified Cafe queue</p>
          <h2>Live Orders</h2>
          <p className="page-description">QR and staff orders share one backend queue. Changes refresh every five seconds while this tab is visible.</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => void load()}>Refresh</button>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <div className="filter-row">
        <label>Status <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | CafeOrderStatus)}><option value="all">All active</option>{ACTIVE.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>Source <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}><option value="all">All sources</option><option value="qr_customer">QR customer</option><option value="order_taker">Order taker</option><option value="billing_counter">Counter</option><option value="manager">Manager</option></select></label>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Order</th><th>Source</th><th>Table/type</th><th>Age</th><th>Status</th><th>Items</th><th>Notes</th><th>Actions</th></tr></thead>
          <tbody>
            {visible.map((order) => (
              <tr key={order.public_id}>
                <td>{order.order_number}</td>
                <td>{order.source_channel}</td>
                <td>{order.table_code ?? order.order_type}</td>
                <td>{ageLabel(order.placed_at)}</td>
                <td>{order.status}</td>
                <td>{order.items.map((item) => `${item.quantity}× ${item.name} [${item.preparation_area}]`).join(", ")}</td>
                <td>{order.customer_notes ?? "—"}</td>
                <td>
                  <div className="action-row">
                    {order.status === "placed" ? <><button type="button" onClick={() => void act(order, "accept")}>Accept</button><button type="button" className="danger-button" onClick={() => void reasonAction(order, "reject")}>Reject</button></> : null}
                    {order.status === "accepted" ? <button type="button" onClick={() => void act(order, "start-preparing")}>Start preparing</button> : null}
                    {order.status === "preparing" ? <button type="button" onClick={() => void act(order, "mark-ready")}>Mark ready</button> : null}
                    {order.status === "ready" ? <button type="button" onClick={() => void act(order, "serve")}>Serve</button> : null}
                    {order.status === "served" ? <button type="button" onClick={() => void requestBill(order)}>Request bill</button> : null}
                    {["placed", "accepted", "preparing"].includes(order.status) && user?.server_role !== "analyst" ? <button type="button" className="danger-button" onClick={() => void reasonAction(order, "cancel")}>Cancel</button> : null}
                  </div>
                </td>
              </tr>
            ))}
            {!visible.length ? <tr><td colSpan={8}>No active Cafe orders match these filters.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}