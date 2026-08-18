import { useEffect, useState } from "react";

import { PublicCafeApiError, type PublicMenu, type PublicOrder } from "../api/publicCafeClient";
import { openCloudCafeSession, openPublicCafeSession, type PublicCafeSession } from "../api/publicCafeSession";

export type CafeSessionState = "loading" | "ready" | "cloud_continuity" | "invalid" | "offline";

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
      .catch(async (operationalError: unknown) => {
        if (cancelled) return;
        try {
          const cloudSession = await openCloudCafeSession(qrToken);
          if (cancelled) return;
          setSession(cloudSession);
          await refresh(cloudSession);
          if (!cancelled) setState("cloud_continuity");
        } catch (cloudError: unknown) {
          if (cancelled) return;
          const error = cloudError instanceof PublicCafeApiError ? cloudError : operationalError;
          setState(error instanceof PublicCafeApiError && [400, 401, 404, 422].includes(error.status) ? "invalid" : "offline");
        }
      });
    return () => { cancelled = true; };
  }, [qrToken]);

  useEffect(() => {
    if (!session || !["ready", "cloud_continuity"].includes(state)) return;
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
