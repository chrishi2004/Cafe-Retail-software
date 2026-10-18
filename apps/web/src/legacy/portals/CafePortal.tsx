import type { AuthUser } from "../auth/types";
import { activeVentureStorage } from "../api/client";
import { SettingsWithTaxPage } from "../pages/SettingsWithTaxPage";
import { CafeBillingPage } from "../pages/CafeBillingPage";
import { CafePOSPage } from "../pages/CafePOSPage";
import { CafeClosingPage } from "../pages/CafeClosingPage";
import { CafeDashboardPage } from "../pages/CafeDashboardPage";
import { CafeKitchenPage } from "../pages/CafeKitchenPage";
import { CafeLiveOrdersPage } from "../pages/CafeLiveOrdersPage";
import { CafeMenuPage } from "../pages/CafeMenuPage";
import { CafeNewOrderPage } from "../pages/CafeNewOrderPage";
import { CafeReceiptHistoryPage } from "../pages/CafeReceiptHistoryPage";
import { CafeReportsPage } from "../pages/CafeReportsPage";
import { CafeTablesPage } from "../pages/CafeTablesPage";
import { InventoryPage } from "../pages/InventoryPage";
import { allowedCafeSections } from "../portalRouting";
import { PortalFrame } from "./PortalFrame";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  orders: "Live Orders",
  pos: "Café POS",
  "new-order": "Table Order",
  tables: "Tables & QR",
  menu: "Menu",
  inventory: "Inventory",
  billing: "Billing",
  reports: "Reports",
  receipts: "Receipt history",
  settings: "Settings",
  closing: "Daily Closing",
  kitchen: "Kitchen",
};

type CafePortalProps = {
  user: AuthUser;
  pathname: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
};

export function CafePortal({
  user,
  pathname,
  onNavigate,
  onLogout,
}: CafePortalProps) {
  const sections =
    user.server_role === "super_admin"
      ? [
          "dashboard",
          "orders",
          "pos",
          "new-order",
          "tables",
          "menu",
          "inventory",
          "billing",
          "receipts",
          "reports",
          "settings",
          "closing",
          "kitchen",
        ]
      : allowedCafeSections(user.server_role);
  const requested =
    pathname.split("/").filter(Boolean)[1] ?? sections[0] ?? "dashboard";
  const active = sections.includes(requested)
    ? requested
    : (sections[0] ?? "dashboard");

  let content;
  if (active === "dashboard") content = <CafeDashboardPage />;
  else if (active === "orders") content = <CafeLiveOrdersPage />;
  else if (active === "pos") content = <CafePOSPage />;
  else if (active === "new-order") content = <CafeNewOrderPage />;
  else if (active === "billing") content = <CafeBillingPage />;
  else if (active === "kitchen") content = <CafeKitchenPage />;
  else if (active === "menu") content = <CafeMenuPage />;
  else if (active === "inventory") content = <InventoryPage />;
  else if (active === "tables") content = <CafeTablesPage />;
  else if (active === "receipts") content = <CafeReceiptHistoryPage />;
  else if (active === "reports") content = <CafeReportsPage />;
  else if (active === "settings") content = <SettingsWithTaxPage />;
  else if (active === "closing") content = <CafeClosingPage />;
  else content = <CafeDashboardPage />;

  return (
    <PortalFrame
      title="Kalpvriksh Cafe"
      subtitle="Cafe operations portal"
      user={user}
      items={sections.map((key) => ({ key, label: LABELS[key] ?? key }))}
      activeKey={active}
      onNavigate={(key) => onNavigate(`/cafe/${key}`)}
      onLogout={onLogout}
      onSwitchVenture={
        user.server_role === "super_admin"
          ? () => {
              activeVentureStorage.clear();
              onNavigate("/super-admin/ventures");
            }
          : undefined
      }
    >
      {content}
    </PortalFrame>
  );
}
