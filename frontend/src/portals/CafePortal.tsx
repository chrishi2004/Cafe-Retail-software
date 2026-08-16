import type { AuthUser } from "../auth/types";
import { TaxOperationPanel } from "../components/TaxOperationPanel";
import { CafeBillingPage } from "../pages/CafeBillingPage";
import { CafeContinuityPage } from "../pages/CafeContinuityPage";
import { CafeKitchenPage } from "../pages/CafeKitchenPage";
import { CafeLiveOrdersPage } from "../pages/CafeLiveOrdersPage";
import { CafeMenuPage } from "../pages/CafeMenuPage";
import { CafeNewOrderPage } from "../pages/CafeNewOrderPage";
import { CafeTablesPage } from "../pages/CafeTablesPage";
import { allowedCafeSections } from "../portalRouting";
import { PortalFrame } from "./PortalFrame";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  orders: "Live Orders",
  pos: "New Order",
  tables: "Tables & QR",
  menu: "Menu",
  billing: "Billing",
  reports: "Reports",
  staff: "Staff",
  settings: "Settings",
  kitchen: "Kitchen",
};

type CafePortalProps = {
  user: AuthUser;
  pathname: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
};

function Placeholder({ user, active }: { user: AuthUser; active: string }) {
  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Cafe workspace</p>
          <h2>{LABELS[active]}</h2>
          <p className="page-description">This section remains intentionally gated for its later approved phase.</p>
        </div>
      </div>
      <article className="panel wide">
        <div className="panel-header"><div><p className="eyebrow">Access scope</p><h3>{user.company_name ?? "Selected Cafe venture"}</h3></div></div>
        <p className="page-description">Role: {user.server_role}. Company and branch authorization is enforced by the backend scope boundary.</p>
      </article>
    </section>
  );
}

export function CafePortal({ user, pathname, onNavigate, onLogout }: CafePortalProps) {
  const sections = user.server_role === "super_admin"
    ? ["dashboard", "orders", "pos", "tables", "menu", "billing", "reports", "staff", "settings", "kitchen"]
    : allowedCafeSections(user.server_role);
  const requested = pathname.split("/").filter(Boolean)[1] ?? sections[0] ?? "dashboard";
  const active = sections.includes(requested) ? requested : sections[0] ?? "dashboard";

  let content;
  if (active === "dashboard") content = <CafeContinuityPage />;
  else if (active === "orders") content = <CafeLiveOrdersPage />;
  else if (active === "pos") content = <CafeNewOrderPage />;
  else if (active === "billing") content = <CafeBillingPage />;
  else if (active === "kitchen") content = <CafeKitchenPage />;
  else if (active === "menu") content = <CafeMenuPage />;
  else if (active === "tables") content = <CafeTablesPage />;
  else if (active === "settings") content = <TaxOperationPanel />;
  else content = <Placeholder user={user} active={active} />;

  return (
    <PortalFrame
      title="Kalpvrik Cafe"
      subtitle="Cafe operations portal"
      user={user}
      items={sections.map((key) => ({ key, label: LABELS[key] ?? key }))}
      activeKey={active}
      onNavigate={(key) => onNavigate(`/cafe/${key}`)}
      onLogout={onLogout}
    >
      {content}
    </PortalFrame>
  );
}
