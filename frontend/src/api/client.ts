import { normalizeAuthUser, type LoginResponse, type ServerLoginResponse } from "../auth/types";
import type { ApiErrorResponse } from "../types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code = "api_error") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function parseApiError(response: Response): Promise<ApiError> {
  let payload: ApiErrorResponse | null = null;
  try {
    payload = (await response.json()) as ApiErrorResponse;
  } catch {
    payload = null;
  }

  const message =
    payload?.error?.message ??
    (typeof payload?.detail === "string" ? payload.detail : null) ??
    "The server could not complete the request.";
  const code = payload?.error?.code ?? "api_error";
  return new ApiError(message, response.status, code);
}

export const activeVentureStorage = {
  key: "hybrid_retail_active_venture_id",
  get(): number | null {
    const raw = window.sessionStorage.getItem(this.key);
    if (!raw) return null;
    const value = Number(raw);
    return Number.isInteger(value) && value > 0 ? value : null;
  },
  set(companyId: number): void {
    window.sessionStorage.setItem(this.key, String(companyId));
  },
  clear(): void {
    window.sessionStorage.removeItem(this.key);
  },
};

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
    if (!headers.has("X-Venture-Id")) {
      const activeVentureId = activeVentureStorage.get();
      if (activeVentureId !== null) {
        headers.set("X-Venture-Id", String(activeVentureId));
      }
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  return (await response.json()) as T;
}

export async function loginRequest(
  email: string,
  password: string,
  totpCode?: string,
  recoveryCode?: string,
): Promise<LoginResponse> {
  const response = await apiRequest<ServerLoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      totp_code: totpCode?.trim() || undefined,
      recovery_code: recoveryCode?.trim() || undefined,
    }),
  });
  return {
    ...response,
    user: normalizeAuthUser(response.user),
  };
}

export const authTokenStorage = {
  key: "hybrid_retail_auth_token",
  get(): string | null {
    return window.sessionStorage.getItem(this.key);
  },
  set(token: string): void {
    window.sessionStorage.setItem(this.key, token);
  },
  clear(): void {
    window.sessionStorage.removeItem(this.key);
  },
};