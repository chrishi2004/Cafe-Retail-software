# Privileged MFA Production Setup

Production defaults to requiring TOTP MFA for `super_admin` and venture `admin` accounts.
Do not publicly expose privileged login until those accounts are enrolled.

## Why console bootstrap exists

A brand-new privileged account cannot safely be allowed to bypass MFA over the public login
route merely to enroll. The Local Hub therefore provides a trusted-console bootstrap command.
It writes only an encrypted TOTP secret and hashed recovery codes to PostgreSQL.

## Enroll from the trusted Local Hub console

Load the same production environment used by the API so `SECRET_KEY` and database settings
match the running service:

```bash
cd /opt/kalpvrik/backend
set -a; source /etc/kalpvrik/local-hub.env; set +a
.venv/bin/python -m scripts.bootstrap_mfa begin --email owner@example.com
```

The command prints:

- an `otpauth://` provisioning URI;
- the manual authenticator secret;
- eight one-time recovery codes.

Add the account to an authenticator application and store the recovery codes offline in a
secure location. They are never stored in plaintext by the application.

Confirm enrollment with a current six-digit code:

```bash
.venv/bin/python -m scripts.bootstrap_mfa confirm --email owner@example.com --code 123456
```

Confirmation enables MFA and increments `token_version`, revoking existing access tokens.

## Login behavior

After enrollment, privileged login requires:

1. email;
2. password;
3. current six-digit TOTP code, or a one-time recovery code.

Recovery codes are removed from the stored hash list after successful use.

## Application enrollment endpoints

Authenticated private/local sessions can also use:

- `POST /api/auth/mfa/enroll`;
- `POST /api/auth/mfa/confirm`;
- `POST /api/auth/mfa/disable`.

Disabling MFA requires the account password and a valid current TOTP code, revokes existing
sessions, and must not be used as a production bypass.

## Secret rotation warning

TOTP secrets are encrypted using a key derived from the application's `SECRET_KEY`. Changing
`SECRET_KEY` without a controlled MFA re-enrollment plan makes existing encrypted TOTP
secrets undecryptable. Treat production `SECRET_KEY` rotation as an operator migration,
not a casual environment edit.

## Release evidence

Before public Super Admin/Venture Admin exposure:

- confirm every privileged production account reports `mfa_enabled=true`;
- test successful TOTP login;
- test missing/incorrect TOTP denial;
- test one recovery code once and verify replay fails;
- retain no screenshots/logs containing the TOTP secret or recovery codes.
