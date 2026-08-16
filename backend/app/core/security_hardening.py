from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import monotonic
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import DeploymentMode, Settings

ASGIApp = Callable[[Request], Awaitable[Response]]


class RequestRateLimiter:
    """Small process-local guard for auth endpoints.

    Public Cafe writes retain their existing database-backed limiter. This
    limiter covers credential endpoints before a database session is opened.
    Production deployments should also enforce limits at the edge.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[tuple[str, str], list[float]] = defaultdict(list)

    def allow(self, *, bucket: str, identity: str, limit: int, window_seconds: int) -> bool:
        now = monotonic()
        key = (bucket, identity)
        with self._lock:
            events = [event for event in self._events[key] if event > now - window_seconds]
            if len(events) >= limit:
                self._events[key] = events
                return False
            events.append(now)
            self._events[key] = events
            if len(self._events) > 4096:
                self._events = {
                    item: values
                    for item, values in self._events.items()
                    if values and values[-1] > now - window_seconds
                }
            return True


class SecurityHardeningMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings, limiter: RequestRateLimiter | None = None) -> None:
        super().__init__(app)
        self.settings = settings
        self.limiter = limiter or RequestRateLimiter()

    @staticmethod
    def _client_identity(request: Request) -> str:
        # Do not trust X-Forwarded-For until a trusted proxy list is configured.
        return request.client.host if request.client else "unknown"

    def _auth_limit(self, request: Request) -> tuple[int, int] | None:
        if request.method.upper() != "POST":
            return None
        path = request.url.path.rstrip("/")
        if path.endswith("/auth/login"):
            return (10, 60)
        if path.endswith("/auth/step-up") or path.endswith("/governance/step-up"):
            return (10, 60)
        return None

    async def dispatch(self, request: Request, call_next: ASGIApp) -> Response:
        limit = self._auth_limit(request)
        if limit:
            allowed = self.limiter.allow(
                bucket=request.url.path,
                identity=self._client_identity(request),
                limit=limit[0],
                window_seconds=limit[1],
            )
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={"error": {"code": "rate_limited", "message": "Too many authentication attempts. Try again later."}},
                    headers={"Retry-After": str(limit[1])},
                )
                self._add_security_headers(response)
                return response

        response = await call_next(request)
        self._add_security_headers(response)
        return response

    def _add_security_headers(self, response: Response) -> None:
        if not self.settings.security_headers_enabled:
            return
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none';",
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.settings.environment.lower() in {"production", "prod"}:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def validate_production_security_settings(settings: Settings) -> None:
    if settings.environment.lower() not in {"production", "prod"}:
        return
    if settings.secret_key in {"", "change-me-in-development"}:
        raise ValueError("SECRET_KEY must be replaced before production startup.")
    if settings.resolved_api_docs_enabled:
        raise ValueError("API docs must be disabled before production startup.")
    if not settings.cors_origins:
        raise ValueError("At least one explicit production CORS origin is required.")
    if any("*" in origin for origin in settings.cors_origins):
        raise ValueError("Wildcard CORS origins are not allowed in production.")
