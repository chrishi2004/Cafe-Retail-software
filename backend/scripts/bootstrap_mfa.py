from __future__ import annotations

import argparse
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.mfa import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    hash_recovery_code,
    new_totp_secret,
    provisioning_uri,
    verify_totp,
)
from app.db.session import SessionLocal
from app.models import User, UserRole

PRIVILEGED_ROLES = {UserRole.SUPER_ADMIN, UserRole.ADMIN}


def begin(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise SystemExit("User not found.")
        if user.role not in PRIVILEGED_ROLES:
            raise SystemExit("Console bootstrap is restricted to privileged admin roles.")
        if user.mfa_enabled:
            raise SystemExit("MFA is already enabled for this account.")

        secret = new_totp_secret()
        recovery_codes = generate_recovery_codes()
        user.mfa_secret_encrypted = encrypt_totp_secret(secret, settings.secret_key)
        user.mfa_recovery_hashes = [hash_recovery_code(code) for code in recovery_codes]
        user.mfa_enrolled_at = None
        db.commit()

        print("MFA enrollment started for:", user.email)
        print("Provisioning URI:")
        print(provisioning_uri(email=user.email, secret=secret))
        print("Manual secret:")
        print(secret)
        print("Recovery codes (shown once; store securely):")
        for code in recovery_codes:
            print(code)
        print("After adding the account to your authenticator, run:")
        print(f"python -m scripts.bootstrap_mfa confirm --email {user.email} --code <6-digit-code>")


def confirm(email: str, code: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise SystemExit("User not found.")
        if user.role not in PRIVILEGED_ROLES:
            raise SystemExit("Console bootstrap is restricted to privileged admin roles.")
        if not user.mfa_secret_encrypted:
            raise SystemExit("No pending MFA enrollment exists. Run the begin action first.")
        try:
            secret = decrypt_totp_secret(user.mfa_secret_encrypted, settings.secret_key)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if not verify_totp(secret, code):
            raise SystemExit("Authenticator code is invalid.")

        user.mfa_enabled = True
        user.mfa_enrolled_at = datetime.now(UTC)
        user.token_version += 1
        db.commit()
        print("MFA enabled for:", user.email)
        print("Existing access tokens were revoked by token-version increment.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap privileged TOTP MFA from the trusted Local Hub console.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    begin_parser = subparsers.add_parser("begin")
    begin_parser.add_argument("--email", required=True)

    confirm_parser = subparsers.add_parser("confirm")
    confirm_parser.add_argument("--email", required=True)
    confirm_parser.add_argument("--code", required=True)

    args = parser.parse_args()
    if args.action == "begin":
        begin(args.email)
    else:
        confirm(args.email, args.code)


if __name__ == "__main__":
    main()
