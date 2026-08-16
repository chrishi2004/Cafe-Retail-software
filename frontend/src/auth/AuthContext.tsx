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
import { normalizeAuthUser, type AuthUser, type ServerAuthUser } from "./types";

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshCurrentUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() => authTokenStorage.get());

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

    try {
      const currentUser = await apiRequest<ServerAuthUser>("/auth/me", {}, storedToken);
      setToken(storedToken);
      setUser(normalizeAuthUser(currentUser));
      setStatus("authenticated");
    } catch {
      clearAuth();
    }
  }, [clearAuth]);

  useEffect(() => {
    void refreshCurrentUser();
  }, [refreshCurrentUser]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest(email, password);
    activeVentureStorage.clear();
    authTokenStorage.set(response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    setStatus("authenticated");
  }, []);

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
