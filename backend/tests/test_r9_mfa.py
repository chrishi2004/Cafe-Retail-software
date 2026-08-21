from __future__ import annotations

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.mfa import (
    consume_recovery_code,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    hash_recovery_code,
    new_totp_secret,
    verify_totp,
)
from app.models import User


def _login(client, *, email: str = "admin@hybridretail.test", password: str = "RetailDemo@123", totp_code: str | None = None):
    payload: dict[str, str] = {"email": email, "password": password}
    if totp_code:
        payload["totp_code"] = totp_code
    return client.post("/api/auth/login", json=payload)


def test_totp_secret_encryption_round_trip_and_wrong_key_fails() -> None:
    secret = new_totp_secret()
    encrypted = encrypt_totp_secret(secret, "one-production-secret")

    assert secret not in encrypted
    assert decrypt_totp_secret(encrypted, "one-production-secret") == secret

    try:
        decrypt_totp_secret(encrypted, "different-production-secret")
    except ValueError:
        pass
    else:
        raise AssertionError("MFA ciphertext must not decrypt under a different application secret")


def test_totp_and_recovery_codes_are_one_time_capable() -> None:
    secret = new_totp_secret()
    current_code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, current_code)
    assert not verify_totp(secret, "000000") or current_code == "000000"

    recovery = generate_recovery_codes(2)
    hashes = [hash_recovery_code(code) for code in recovery]
    matched, remaining = consume_recovery_code(hashes, recovery[0])
    assert matched is True
    assert len(remaining) == 1
    matched_again, _ = consume_recovery_code(remaining, recovery[0])
    assert matched_again is False


def test_privileged_mfa_policy_defaults_on_in_production() -> None:
    development = Settings(environment="development")
    production = Settings(environment="production", secret_key="release-test-secret")
    explicit_override = Settings(
        environment="production",
        secret_key="release-test-secret",
        require_privileged_mfa=False,
    )

    assert development.resolved_require_privileged_mfa is False
    assert production.resolved_require_privileged_mfa is True
    assert explicit_override.resolved_require_privileged_mfa is False


def test_admin_can_enroll_confirm_and_login_with_totp(client, db_session_factory: sessionmaker[Session]) -> None:
    initial = _login(client)
    assert initial.status_code == 200
    token = initial.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    enroll = client.post("/api/auth/mfa/enroll", headers=headers)
    assert enroll.status_code == 200
    enrollment = enroll.json()
    assert enrollment["secret"]
    assert enrollment["provisioning_uri"].startswith("otpauth://totp/")
    assert len(enrollment["recovery_codes"]) == 8

    confirm_code = pyotp.TOTP(enrollment["secret"]).now()
    confirm = client.post("/api/auth/mfa/confirm", headers=headers, json={"totp_code": confirm_code})
    assert confirm.status_code == 200

    without_code = _login(client)
    assert without_code.status_code == 401

    with_code = _login(client, totp_code=pyotp.TOTP(enrollment["secret"]).now())
    assert with_code.status_code == 200
    assert with_code.json()["user"]["mfa_enabled"] is True

    with db_session_factory() as db:
        user = db.scalar(select(User).where(User.email == "admin@hybridretail.test"))
        assert user is not None
        assert user.mfa_enabled is True
        assert user.mfa_secret_encrypted
        assert enrollment["secret"] not in user.mfa_secret_encrypted
        assert enrollment["recovery_codes"][0] not in (user.mfa_recovery_hashes or [])
