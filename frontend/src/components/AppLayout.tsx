import { Building2, LogOut, Menu, ShieldCheck, X } from "lucide-react";
import { type PropsWithChildren, useMemo, useState } from "react";

import type { AuthUser } from "../auth/types";
import { ROLE_LABELS, getVisibleNavItems } from "../navigation";
import type { RouteKey } from "../types";

type AppLayoutProps = PropsWithChildren<{
  activeRoute: RouteKey;
  onNavigate: (route: RouteKey) => void;
  user: AuthUser;
  onLogout: () => void;
  onSwitchVenture?: () => void;
}>;

export function AppLayout({
  activeRoute,
  onNavigate,
  user,
  onLogout,
  onSwitchVenture,
  children,
}: AppLayoutProps) {
  const [navOpen, setNavOpen] = useState(false);
  const visibleNavItems = useMemo(() => getVisibleNavItems(user.role), [user.role]);

  const handleNavigate = (route: RouteKey) => {
    onNavigate(route);
    setNavOpen(false);
  };

  return (
    <main className="app-shell">
      <aside className={navOpen ? "sidebar open" : "sidebar"} aria-label="Main navigation">
        <div className="brand-block">
          <div className="brand-mark">KR</div>
          <div>
            <p className="brand-name">Kalpvrik Retail</p>
            <p className="brand-subtitle">Retail operations portal</p>
          </div>
          <button
            aria-label="Close navigation"
            className="icon-button nav-close"
            onClick={() => setNavOpen(false)}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        <nav className="nav-list">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.key === activeRoute;
            return (
              <button
                aria-current={isActive ? "page" : undefined}
                className={isActive ? "nav-item active" : "nav-item"}
                key={item.key}
                onClick={() => handleNavigate(item.key)}
                title={item.label}
                type="button"
              >
                <Icon aria-hidden="true" size={18} />
                <span>{item.shortLabel ?? item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      {navOpen ? (
        <button
          aria-label="Close navigation overlay"
          className="nav-backdrop"
          onClick={() => setNavOpen(false)}
          type="button"
        />
      ) : null}

      <section className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              aria-label="Open navigation"
              className="icon-button nav-toggle"
              onClick={() => setNavOpen(true)}
              type="button"
            >
              <Menu aria-hidden="true" size={19} />
            </button>
            <div>
              <p className="eyebrow">Retail workspace</p>
              <h1>{user.company_name ?? "Retail operations"}</h1>
            </div>
          </div>

          <div className="user-cluster">
            <div className="user-badge">
              <ShieldCheck aria-hidden="true" size={17} />
              <div>
                <strong>{user.name}</strong>
                <span>{ROLE_LABELS[user.role]}</span>
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
