import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "./auth/AuthContext";
import { activeVentureStorage } from "./api/client";
import { AppLayout } from "./components/AppLayout";
import { ErrorState, LoadingState } from "./components/ui";
import { canAccessRoute, getDefaultRoute } from "./navigation";
import { AIAssistantPage } from "./pages/AIAssistantPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ForecastingPage } from "./pages/ForecastingPage";
import { InventoryPage } from "./pages/InventoryPage";
import { LoginPage } from "./pages/LoginPage";
import { LowStockReorderPage } from "./pages/LowStockReorderPage";
import { MasterDataPage, isMasterDataRoute } from "./pages/MasterDataPage";
import { OverviewDashboardPage } from "./pages/OverviewDashboardPage";
import { POSPage } from "./pages/POSPage";
import { PowerBIReportsPage } from "./pages/PowerBIReportsPage";
import { PurchaseOrdersDashboardPage } from "./pages/PurchaseOrdersDashboardPage";
import { SalesPage } from "./pages/SalesPage";
import { SettingsWithTaxPage } from "./pages/SettingsWithTaxPage";
import type { DashboardRouteKey } from "./pages/pageContent";
import type { RouteKey } from "./types";

import "./styles.css";

const ROUTE_KEYS: RouteKey[] = [
  "overview",
  "products",
  "customers",
  "pos",
  "sales",
  "inventory",
  "low-stock",
  "purchase-orders",
  "suppliers",
  "categories",
  "branches",
  "forecasting",
  "ai-assistant",
  "power-bi",
  "settings",
];

function getRouteFromHash(): RouteKey {
  const rawRoute = window.location.hash.replace(/^#\/?/, "");
  return ROUTE_KEYS.includes(rawRoute as RouteKey) ? (rawRoute as RouteKey) : "overview";
}

function App() {
  const { status, user, logout } = useAuth();
  const [activeRoute, setActiveRoute] = useState<RouteKey>(() => getRouteFromHash());
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    const handleHashChange = () => setActiveRoute(getRouteFromHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const availableRoute = useMemo(() => {
    if (!user) return activeRoute;
    return canAccessRoute(user.role, activeRoute) ? activeRoute : getDefaultRoute(user.role);
  }, [activeRoute, user]);

  useEffect(() => {
    if (user && availableRoute !== activeRoute) {
      window.location.hash = `/${availableRoute}`;
      setActiveRoute(availableRoute);
    }
  }, [activeRoute, availableRoute, user]);

  const navigate = useCallback((route: RouteKey) => {
    window.location.hash = `/${route}`;
    setActiveRoute(route);
  }, []);

  const handleLogout = useCallback(async () => {
    setLogoutError(null);
    try {
      await logout();
      window.location.hash = "";
    } catch {
      setLogoutError("Logout could not reach the API. Your local session was kept active.");
    }
  }, [logout]);

  const handleSwitchVenture = useCallback(() => {
    activeVentureStorage.clear();
    window.location.assign("/super-admin/ventures");
  }, []);

  if (status === "checking") return <LoadingState label="Checking session" />;
  if (status === "unauthenticated" || !user) return <LoginPage />;

  return (
    <AppLayout
      activeRoute={availableRoute}
      onLogout={handleLogout}
      onNavigate={navigate}
      onSwitchVenture={user.server_role === "super_admin" ? handleSwitchVenture : undefined}
      user={user}
    >
      {logoutError ? <ErrorState message={logoutError} title="Logout failed" /> : null}
      {isMasterDataRoute(availableRoute) ? (
        <MasterDataPage routeKey={availableRoute} />
      ) : availableRoute === "customers" ? (
        <CustomersPage />
      ) : availableRoute === "pos" ? (
        <POSPage />
      ) : availableRoute === "overview" ? (
        <OverviewDashboardPage />
      ) : availableRoute === "inventory" ? (
        <InventoryPage />
      ) : availableRoute === "low-stock" ? (
        <LowStockReorderPage />
      ) : availableRoute === "sales" ? (
        <SalesPage />
      ) : availableRoute === "purchase-orders" ? (
        <PurchaseOrdersDashboardPage />
      ) : availableRoute === "forecasting" ? (
        <ForecastingPage />
      ) : availableRoute === "ai-assistant" ? (
        <AIAssistantPage />
      ) : availableRoute === "power-bi" ? (
        <PowerBIReportsPage />
      ) : availableRoute === "settings" ? (
        <SettingsWithTaxPage />
      ) : (
        <DashboardPage role={user.role} routeKey={availableRoute as DashboardRouteKey} />
      )}
    </AppLayout>
  );
}

export default App;
