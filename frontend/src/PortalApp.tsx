import { useEffect, useState } from "react";

import App from "./App";
import { activeVentureStorage } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { defaultPathForUser, portalFromPath, safePathForUser } from "./portalRouting";
import { CafePortal } from "./portals/CafePortal";
import { SuperAdminPortal } from "./portals/SuperAdminPortal";
import { CustomerMenuEntry } from "./public/CustomerMenuEntry";

export default function PortalApp() {
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
  if (publicOrderMatch) return <CustomerMenuEntry />;

  if (auth.status !== "authenticated" || !auth.user || !auth.token) {
    return <App />;
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

  // Existing Retail functionality remains intact inside the isolated /retail shell.
  // Its internal hash navigation is preserved in P3 to avoid breaking bookmarks.
  return <App />;
}
