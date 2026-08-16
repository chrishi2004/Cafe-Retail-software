import { useEffect, useState } from "react";

import { PublicCafeApiError, type PublicMenu, type PublicOrder } from "../api/publicCafeClient";
import { openPublicCafeSession, type PublicCafeSession } from "../api/publicCafeSession";

export type CafeSessionState = "loading" | "ready" | "invalid" | "offline";

export function useCafeSession(qrToken: string) {
  const [state, setState] = useState<CafeSessionState>("loading");
  const [session, setSession] = useState<PublicCafeSession | null>(null);
  const [menu, setMenu] = useState<PublicMenu | null>(null);
  const [orders, setOrders] = useState<PublicOrder[]>([]);
  const [sessionStatus, setSessionStatus] = useState("open");

  const refresh = async (active: PublicCafeSession) => {
    const [nextMenu, nextOrders] = await Promise.all([active.menu(), active.orders()]);
    setMenu(nextMenu);
    setOrders(nextOrders.orders);
    setSessionStatus(nextOrders.session_status);
  };

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    openPublicCafeSession(qrToken)
      .then(async (active) => {
        if (cancelled) return;
        setSession(active);
        await refresh(active);
        if (!cancelled) setState("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState(error instanceof PublicCafeApiError && [401, 404].includes(error.status) ? "invalid" : "offline");
      });
    return () => { cancelled = true; };
  }, [qrToken]);

  useEffect(() => {
    if (!session || state !== "ready") return;
    let timer: number | undefined;
    const poll = async () => {
      if (document.visibilityState !== "visible") return;
      const next = await session.orders();
      setOrders(next.orders);
      setSessionStatus(next.session_status);
    };
    const schedule = () => {
      window.clearInterval(timer);
      if (document.visibilityState === "visible") timer = window.setInterval(() => void poll(), 7000);
    };
    document.addEventListener("visibilitychange", schedule);
    schedule();
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", schedule); };
  }, [session, state]);

  return { state, session, menu, orders, sessionStatus, refresh };
}
