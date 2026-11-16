import { useEffect, useState } from "react";

import { activeVentureStorage, apiRequest } from "../api/client";
import { getCombinedTurnover, type CombinedTurnover } from "../api/taxOperation";
import { ConsolidatedDashboardPage } from "../pages/ConsolidatedDashboardPage";
import { AuditPage } from "../pages/AuditPage";
import { EmployeesPage } from "../pages/EmployeesPage";
import { PurgeReviewPage } from "../pages/PurgeReviewPage";
import { type AuthUser, type BusinessType } from "../auth/types";
import { PortalFrame } from "./PortalFrame";

type Venture = {
  id: number;
  business_group_id: number;
  business_type: BusinessType;
  slug: string;
  code: string;
  name: string;
  legal_name: string;
  trade_name: string | null;
  is_active: boolean;
};

type SuperAdminPortalProps = {
  user: AuthUser;
  token: string;
  pathname: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
};

function money(value: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value) || 0);
}

const PAGE_TITLES = {
  ventures: "Choose a business workspace",
  dashboard: "Consolidated business dashboard",
  purge: "Protected data removal review",
  users: "Team access and roles",
  audit: "Activity & Audit",
} as const;

export function SuperAdminPortal({ user, token, pathname, onNavigate, onLogout }: SuperAdminPortalProps) {
  const active = pathname.includes("/audit") ? "audit" : pathname.includes("/users") ? "users" : pathname.includes("/dashboard") ? "dashboard" : pathname.includes("/purge") ? "purge" : "ventures";
  const [ventures, setVentures] = useState<Venture[]>([]);
  const [turnover, setTurnover] = useState<CombinedTurnover | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    activeVentureStorage.clear();
    setError(null);
    void Promise.all([
      apiRequest<Venture[]>( "/ventures", {}, token),
      getCombinedTurnover(token),
    ])
      .then(([ventureRows, turnoverSummary]) => {
        setVentures(ventureRows);
        setTurnover(turnoverSummary);
      })
      .catch((err: Error) => setError(err.message));
  }, [token]);

  const enterVenture = (venture: Venture) => {
    activeVentureStorage.set(venture.id);
    onNavigate(venture.business_type === "cafe" ? "/cafe/dashboard" : "/retail/overview");
  };

  return (
    <PortalFrame
      title="Super Admin"
      subtitle="Owner control centre"
      user={user}
      items={[{ key: "ventures", label: "Ventures" }, { key: "dashboard", label: "Consolidated Dashboard" }, { key: "purge", label: "Purge Review" }, { key: "users", label: "Users" }, { key: "audit", label: "Activity & Audit" }]}
      activeKey={active}
      onNavigate={(key) => onNavigate(`/super-admin/${key}`)}
      onLogout={onLogout}
    >
      <section className="page-stack">
        <div className="page-header">
          <div>
            <p className="eyebrow">Owner workspace · All businesses</p>
            <h2>{PAGE_TITLES[active]}</h2>
            {active !== "audit" && <p className="page-description">
              Start here to open Retail or Cafe operations. Team members skip this screen and
              enter only the workspace allowed by their assigned role and branch.
            </p>}
          </div>
        </div>
        {error ? <article className="panel"><p>{error}</p></article> : null}
        {active === "audit" ? <AuditPage token={token} /> : active === "dashboard" ? <ConsolidatedDashboardPage /> : active === "purge" ? <PurgeReviewPage /> : active === "ventures" ? (
          <>
            {turnover ? (
              <>
                <section className="metric-grid" aria-label="Business group turnover review">
                  {turnover.ventures.map((venture) => (
                    <article className="metric-card blue" key={venture.company_id}>
                      <p>{venture.company_name}</p>
                      <strong>{money(venture.turnover)}</strong>
                      <span>{venture.business_type} recorded turnover</span>
                    </article>
                  ))}
                  <article className="metric-card amber">
                    <p>Combined turnover</p>
                    <strong>{money(turnover.combined_turnover)}</strong>
                    <span>Business Group monitoring total</span>
                  </article>
                </section>
                <div className="state-panel">
                  <p>{turnover.review_notice}</p>
                </div>
              </>
            ) : null}

            <section className="content-grid">
              {ventures.map((venture) => (
                <article className="panel" key={venture.id}>
                  <p className="eyebrow">{venture.business_type === "cafe" ? "Cafe business" : "Retail business"}</p>
                  <h3>{venture.name}</h3>
                  <p className="page-description">
                    {venture.business_type === "cafe"
                      ? "Manage tables, QR ordering, live orders, kitchen, billing, closing and Cafe reports."
                      : "Manage POS billing, products, customers, stock, purchases, forecasting and Retail reports."}
                  </p>
                  <button className="action-button primary" type="button" onClick={() => enterVenture(venture)}>
                    Open {venture.business_type === "cafe" ? "Cafe" : "Retail"} workspace
                  </button>
                </article>
              ))}
            </section>
          </>
        ) : (
          <EmployeesPage />
        )}
      </section>
    </PortalFrame>
  );
}
