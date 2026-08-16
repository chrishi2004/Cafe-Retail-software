import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390_000
ACCESS_TOKEN_ALGORITHM = "HS256"
_INVALIDATED_TOKEN_IDS: dict[str, int] = {}


class TokenError(ValueError):
    """Raised when a bearer token cannot be trusted."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected_digest = base64.b64decode(digest_b64)
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual_digest, expected_digest)


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def _sign_token_payload(payload_b64: str) -> str:
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(signature)


def create_access_token(
    *,
    subject: int,
    role: str,
    token_version: int = 1,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    if token_version < 1:
        raise ValueError("token_version must be at least 1")

    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(16),
        "typ": "access",
    }
    payload_b64 = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature_b64 = _sign_token_payload(payload_b64)
    return f"{payload_b64}.{signature_b64}", expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("Malformed access token") from exc

    expected_signature = _sign_token_payload(payload_b64)
    if not hmac.compare_digest(signature_b64, expected_signature):
        raise TokenError("Invalid access token signature")

    try:
        payload = json.loads(_base64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError) as exc:
        raise TokenError("Invalid access token payload") from exc

    if payload.get("typ") != "access":
        raise TokenError("Invalid token type")

    expires_at = int(payload.get("exp", 0))
    if expires_at <= int(datetime.now(UTC).timestamp()):
        raise TokenError("Access token expired")

    if not payload.get("sub") or not payload.get("jti"):
        raise TokenError("Access token missing required claims")

    try:
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError) as exc:
        raise TokenError("Invalid token version") from exc
    if token_version < 1:
        raise TokenError("Access token missing token version")
    payload["ver"] = token_version

    return payload


def invalidate_access_token(token_id: str, expires_at_timestamp: int) -> None:
    # JTI invalidation remains as a fast single-token compatibility path. P2 also
    # validates the persisted User.token_version so role/company changes and
    # logout stay revoked across process restarts and multiple API instances.
    _prune_invalidated_tokens()
    _INVALIDATED_TOKEN_IDS[token_id] = expires_at_timestamp


def is_access_token_invalidated(token_id: str) -> bool:
    _prune_invalidated_tokens()
    return token_id in _INVALIDATED_TOKEN_IDS


def _prune_invalidated_tokens() -> None:
    now_timestamp = int(datetime.now(UTC).timestamp())
    expired_token_ids = [
        token_id
        for token_id, expires_at in _INVALIDATED_TOKEN_IDS.items()
        if expires_at <= now_timestamp
    ]
    for token_id in expired_token_ids:
        _INVALIDATED_TOKEN_IDS.pop(token_id, None)
