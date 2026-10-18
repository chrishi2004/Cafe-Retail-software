import { Building2, LogOut, ShieldCheck } from "lucide-react";
import type { PropsWithChildren } from "react";

import { SERVER_ROLE_LABELS, type AuthUser } from "../auth/types";

type PortalFrameProps = PropsWithChildren<{
  title: string;
  subtitle: string;
  user: AuthUser;
  items: Array<{ key: string; label: string }>;
  activeKey: string;
  onNavigate: (key: string) => void;
  onLogout: () => void;
  onSwitchVenture?: () => void;
}>;

export function PortalFrame({ title, subtitle, user, items, activeKey, onNavigate, onLogout, onSwitchVenture, children }: PortalFrameProps) {
  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label={`${title} navigation`}>
        <div className="brand-block">
          <div className="brand-mark">KV</div>
          <div>
            <p className="brand-name">{title}</p>
            <p className="brand-subtitle">{subtitle}</p>
          </div>
        </div>
        <nav className="nav-list">
          {items.map((item) => (
            <button
              key={item.key}
              className={item.key === activeKey ? "nav-item active" : "nav-item"}
              aria-current={item.key === activeKey ? "page" : undefined}
              onClick={() => onNavigate(item.key)}
              type="button"
            >
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{subtitle}</p>
            <h1>{title}</h1>
          </div>
          <div className="user-cluster">
            <div className="user-badge">
              <ShieldCheck aria-hidden="true" size={17} />
              <div>
                <strong>{user.name}</strong>
                <span>{SERVER_ROLE_LABELS[user.server_role]} · {user.company_name ?? "All Ventures"}</span>
              </div>
            </div>
            {onSwitchVenture ? (
              <button className="logout-button" onClick={onSwitchVenture} type="button">
                <Building2 aria-hidden="true" size={17} />
                <span>Switch business</span>
              </button>
            ) : null}
            <button className="logout-button" onClick={onLogout} type="button">
              <LogOut aria-hidden="true" size={17} />
              <span>Logout</span>
            </button>
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}
