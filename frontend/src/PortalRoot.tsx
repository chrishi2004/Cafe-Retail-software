import { lazy, Suspense, useEffect, useState } from "react";

import { activeVentureStorage } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { defaultPathForUser, portalFromPath, safePathForUser } from "./portalRouting";
import { CafePortal } from "./portals/CafePortal";
import { SuperAdminPortal } from "./portals/SuperAdminPortal";

// Keep the existing Retail implementation intact. The explicit .tsx import is
// intentional because App.ts is now the P3 entry shim for extensionless imports.
// @ts-ignore Vite supports explicit TSX module imports; tsc otherwise discourages the extension.
const RetailApp = lazy(() => import("./App.tsx"));

function PublicOrderPlaceholder({ token }: { token: string }) {
  return (
    <main className="login-shell">
      <section className="login-card">
        <p className="eyebrow">Kalpvrik Cafe</p>
        <h1>Table ordering is not active yet</h1>
        <p className="page-description">
          QR route recognized for token {token.slice(0, 6)}… . P3 keeps this surface separate from authenticated portals; public ordering remains disabled until the P5, HC2 and P6 gates pass.
        </p>
      </section>
    </main>
  );
}

export default function PortalRoot() {
  const auth = useAuth();
  const [pathname, setPathname] = useState(window.location.pathname || "/");

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname || "/");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (path: string) => {
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
    setPathname(path);
  };

  const publicOrderMatch = pathname.match(/^\/order\/([^/]+)$/);
  if (publicOrderMatch) return <PublicOrderPlaceholder token={publicOrderMatch[1]} />;

  if (auth.status !== "authenticated" || !auth.user || !auth.token) {
    return (
      <Suspense fallback={null}>
        <RetailApp />
      </Suspense>
    );
  }

  const user = auth.user;
  let resolvedPath = safePathForUser(user, pathname);
  const requestedPortal = portalFromPath(resolvedPath);

  if (
    user.server_role === "super_admin" &&
    requestedPortal !== "super-admin" &&
    !activeVentureStorage.get()
  ) {
    resolvedPath = "/super-admin/ventures";
  }

  if (resolvedPath !== pathname) {
    window.history.replaceState({}, "", resolvedPath);
    queueMicrotask(() => setPathname(resolvedPath));
  }

  const portal = portalFromPath(resolvedPath);
  if (!portal) {
    const fallback = defaultPathForUser(user);
    window.history.replaceState({}, "", fallback);
    queueMicrotask(() => setPathname(fallback));
    return null;
  }

  if (portal === "super-admin") {
    return (
      <SuperAdminPortal
        user={user}
        token={auth.token}
        pathname={resolvedPath}
        onNavigate={navigate}
        onLogout={() => void auth.logout()}
      />
    );
  }

  if (portal === "cafe") {
    return (
      <CafePortal
        user={user}
        pathname={resolvedPath}
        onNavigate={navigate}
        onLogout={() => void auth.logout()}
      />
    );
  }

  return (
    <Suspense fallback={null}>
      <RetailApp />
    </Suspense>
  );
}
