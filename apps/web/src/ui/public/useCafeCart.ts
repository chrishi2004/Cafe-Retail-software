import { useMemo, useState } from "react";

import { PublicCafeApiError, type PublicMenu, type PublicMenuItem } from "../api/publicCafeClient";
import type { PublicCafeSession } from "../api/publicCafeSession";

type CartLine = { quantity: number; notes: string };

function newKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `order-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function useCafeCart(menu: PublicMenu | null, session: PublicCafeSession | null, onCommitted: () => Promise<void>) {
  const [cart, setCart] = useState<Record<string, CartLine>>({});
  const [customerNotes, setCustomerNotes] = useState("");
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const itemMap = useMemo(() => new Map((menu?.items ?? []).map((item) => [item.public_id, item])), [menu]);
  const lines = useMemo(() => Object.entries(cart).map(([id, line]) => ({ item: itemMap.get(id), ...line })).filter((line): line is { item: PublicMenuItem; quantity: number; notes: string } => Boolean(line.item)), [cart, itemMap]);
  const total = lines.reduce((sum, line) => sum + Number(line.item.selling_price) * line.quantity, 0);

  const resetRetry = () => { setPendingKey(null); setError(null); setMessage(null); };
  const quantity = (id: string) => cart[id]?.quantity ?? 0;
  const changeQuantity = (id: string, delta: number) => {
    resetRetry();
    setCart((current) => {
      const next = { ...current };
      const value = Math.max(0, Math.min(20, (next[id]?.quantity ?? 0) + delta));
      if (!value) delete next[id]; else next[id] = { quantity: value, notes: next[id]?.notes ?? "" };
      return next;
    });
  };
  const changeLineNote = (id: string, value: string) => {
    resetRetry();
    setCart((current) => ({ ...current, [id]: { ...current[id], notes: value.slice(0, 300) } }));
  };
  const changeCustomerNotes = (value: string) => { resetRetry(); setCustomerNotes(value.slice(0, 500)); };

  const submit = async () => {
    if (!session || !lines.length) return;
    const key = pendingKey ?? newKey();
    setPendingKey(key); setBusy(true); setError(null); setMessage(null);
    try {
      const order = await session.submit(key, {
        items: lines.map((line) => ({ menu_item_public_id: line.item.public_id, quantity: line.quantity, notes: line.notes.trim() || null })),
        customer_notes: customerNotes.trim() || null,
      });
      setCart({}); setCustomerNotes(""); setPendingKey(null); setMessage(`Order ${order.order_number} confirmed.`);
      await onCommitted();
    } catch (failure: unknown) {
      setError(failure instanceof PublicCafeApiError ? failure.message : "The network did not confirm the order. Retry without changing the cart.");
    } finally { setBusy(false); }
  };

  return { lines, total, customerNotes, pendingKey, busy, message, error, quantity, changeQuantity, changeLineNote, changeCustomerNotes, submit, setMessage, setError, setBusy };
}
