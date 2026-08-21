from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime
from urllib.parse import quote

import pyotp
from cryptography.fernet import Fernet, InvalidToken


MFA_ISSUER = "Kalpvrik Business Suite"


def _fernet_key(app_secret: str) -> bytes:
    digest = hashlib.sha256(f"kalpvrik:mfa:v1:{app_secret}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_totp_secret(secret: str, app_secret: str) -> str:
    return Fernet(_fernet_key(app_secret)).encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(ciphertext: str, app_secret: str) -> str:
    try:
        return Fernet(_fernet_key(app_secret)).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise ValueError("Stored MFA secret could not be decrypted.") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32(length=32)


def provisioning_uri(*, email: str, secret: str, issuer: str = MFA_ISSUER) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str, *, valid_window: int = 1) -> bool:
    normalized = "".join(ch for ch in code if ch.isdigit())
    if len(normalized) != 6:
        return False
    return bool(pyotp.TOTP(secret).verify(normalized, valid_window=valid_window))


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().lower().encode("utf-8")).hexdigest()


def consume_recovery_code(stored_hashes: list[str] | None, candidate: str) -> tuple[bool, list[str]]:
    if not stored_hashes:
        return False, []
    candidate_hash = hash_recovery_code(candidate)
    matched = any(secrets.compare_digest(candidate_hash, item) for item in stored_hashes)
    if not matched:
        return False, list(stored_hashes)
    return True, [item for item in stored_hashes if not secrets.compare_digest(candidate_hash, item)]


def utcnow() -> datetime:
    return datetime.now(UTC)
