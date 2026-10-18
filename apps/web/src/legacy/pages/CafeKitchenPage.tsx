import { useCallback, useEffect, useState } from "react";

import type { PreparationArea } from "../api/cafe";
import { listKitchenOrders, transitionCafeOrder, type KitchenOrder } from "../api/cafeOrders";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

const AREAS: Array<PreparationArea | "all"> = ["all", "kitchen", "beverage", "counter"];

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Kitchen queue operation failed.";
}

function ageLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m`;
}

export function CafeKitchenPage() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [area, setArea] = useState<PreparationArea | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const rows = await listKitchenOrders(token, area === "all" ? undefined : area);
      setOrders(rows);
      setError(null);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [area, token]);

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

  const act = async (order: KitchenOrder, action: "start-preparing" | "mark-ready") => {
    if (!token) return;
    try {
      await transitionCafeOrder(token, order.public_id, action, order.version);
      await load();
    } catch (actionError) {
      setError(errorMessage(actionError));
      await load();
    }
  };

  if (loading) return <LoadingState label="Loading Kitchen queue" />;

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Preparation workspace</p>
          <h2>Kitchen Queue</h2>
          <p className="page-description">Only preparation-relevant order data is shown. Prices, billing, payments, customer data, Retail data and margins are intentionally absent.</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => void load()}>Refresh</button>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <div className="filter-row">
        <label>Preparation area <select value={area} onChange={(event) => setArea(event.target.value as PreparationArea | "all")}>{AREAS.map((value) => <option key={value} value={value}>{value === "all" ? "All prep areas" : value}</option>)}</select></label>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Order</th><th>Table</th><th>Age</th><th>Status</th><th>Preparation</th><th>Actions</th></tr></thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.public_id}>
                <td>{order.order_number}</td>
                <td>{order.table_reference ?? "Counter / takeaway"}</td>
                <td>{ageLabel(order.age_seconds)}</td>
                <td>{order.status}</td>
                <td>{order.items.map((item) => `${item.quantity}× ${item.name} · ${item.preparation_area}${item.notes ? ` · ${item.notes}` : ""}`).join(" | ")}</td>
                <td>
                  {order.status === "accepted" ? <button type="button" onClick={() => void act(order, "start-preparing")}>Start preparing</button> : null}
                  {order.status === "preparing" ? <button type="button" onClick={() => void act(order, "mark-ready")}>Mark ready</button> : null}
                  {order.status === "ready" ? <span>Waiting for service</span> : null}
                </td>
              </tr>
            ))}
            {!orders.length ? <tr><td colSpan={6}>No preparation orders are waiting.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
