import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  activeVentureStorage,
  ApiError,
  apiRequest,
  authTokenStorage,
  loginRequest,
} from "../api/client";
import { defaultPathForUser } from "../portalRouting";
import { useRouter } from "next/navigation";
import { normalizeAuthUser, type AuthUser, type ServerAuthUser } from "./types";

type AuthStatus = "checking" | "authenticated" | "unauthenticated" | "unavailable";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  token: string | null;
  login: (
    email: string,
    password: string,
    totpCode?: string,
    recoveryCode?: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  refreshCurrentUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() =>
    authTokenStorage.get(),
  );

  const clearAuth = useCallback(() => {
    authTokenStorage.clear();
    activeVentureStorage.clear();
    setToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const refreshCurrentUser = useCallback(async () => {
    const storedToken = authTokenStorage.get();
    if (!storedToken) {
      clearAuth();
      return;
    }

    setStatus("checking");
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const currentUser = await apiRequest<ServerAuthUser>("/auth/me", {}, storedToken);
        if (authTokenStorage.get() !== storedToken) return;
        setToken(storedToken);
        setUser(normalizeAuthUser(currentUser));
        setStatus("authenticated");
        return;
      } catch (error) {
        if (authTokenStorage.get() !== storedToken) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearAuth();
          return;
        }
      }
    }
    // A cancelled, failed, or incomplete response doesn't revoke a valid session.
    setStatus("unavailable");
  }, [clearAuth]);

  useEffect(() => {
    void refreshCurrentUser();
  }, [refreshCurrentUser]);

  const login = useCallback(
    async (
      email: string,
      password: string,
      totpCode?: string,
      recoveryCode?: string,
    ) => {
      const response = await loginRequest(
        email,
        password,
        totpCode,
        recoveryCode,
      );
      activeVentureStorage.clear();
      authTokenStorage.set(response.access_token);
      router.replace(defaultPathForUser(response.user));
      setToken(response.access_token);
      setUser(response.user);
      setStatus("authenticated");
    },
    [router],
  );

  const logout = useCallback(async () => {
    const currentToken = authTokenStorage.get();
    if (currentToken) {
      try {
        await apiRequest("/auth/logout", { method: "POST" }, currentToken);
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) {
          throw error;
        }
      }
    }
    clearAuth();
  }, [clearAuth]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      token,
      login,
      logout,
      refreshCurrentUser,
    }),
    [status, user, token, login, logout, refreshCurrentUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
