import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import App from "./RetailApplication";
import { activeVentureStorage } from "./api/client";
import { ErrorState } from "./components/ui";
import { useAuth } from "./auth/AuthContext";
import { portalFromPath, safePathForUser } from "./portalRouting";
import { CafePortal } from "./portals/CafePortal";
import { SuperAdminPortal } from "./portals/SuperAdminPortal";

export default function PortalApp() {
  const auth = useAuth();
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const pathname = usePathname() || "/";
  const router = useRouter();

  const navigate = (path: string) => router.push(path);
  const currentUser = auth.user;
  let target = currentUser ? safePathForUser(currentUser, pathname) : pathname;
  if (
    currentUser?.server_role === "super_admin" &&
    portalFromPath(target) !== "super-admin" &&
    !activeVentureStorage.get()
  )
    target = "/super-admin/ventures";
  useEffect(() => {
    if (auth.status === "authenticated" && target !== pathname)
      router.replace(target);
  }, [auth.status, target, pathname, router]);

  const handleLogout = async () => {
    setLogoutError(null);
    try {
      await auth.logout();
    } catch {
      setLogoutError("Logout could not reach the server. Please retry.");
    }
  };

  if (auth.status !== "authenticated" || !auth.user || !auth.token) {
    return <App />;
  }

  const user = auth.user;
  const resolvedPath = target;
  const portal = portalFromPath(resolvedPath);
  if (!portal || resolvedPath !== pathname) return null;

  if (portal === "super-admin") {
    return (
      <SuperAdminPortal
        user={user}
        token={auth.token}
        pathname={resolvedPath}
        onNavigate={navigate}
        onLogout={() => void handleLogout()}
      />
    );
  }

  if (portal === "cafe") {
    return (
      <>
        {logoutError ? <ErrorState message={logoutError} /> : null}
        <CafePortal
          user={user}
          pathname={resolvedPath}
          onNavigate={navigate}
          onLogout={() => void handleLogout()}
        />
      </>
    );
  }

  // Retail screens use Next.js navigation; legacy hash bookmarks redirect in App.
  return <App />;
}
