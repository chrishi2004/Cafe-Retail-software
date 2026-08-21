from __future__ import annotations

import argparse
import hashlib

from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.pool import NullPool

from app.cloud_db.schema import device_registrations
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Branch, BusinessGroup, Company
from app.sync.device import DeviceIdentityStore, SettingsCredentialStore

DEFAULT_PURPOSES = ["heartbeat", "menu_publication", "sync_pull", "sync_push"]


def _resolve_scope(
    *,
    business_group_id: int | None,
    company_id: int | None,
    branch_id: int | None,
) -> tuple[int, int | None, int | None]:
    with SessionLocal() as db:
        if branch_id is not None:
            branch = db.get(Branch, branch_id, execution_options={"scope_bypass": True})
            if branch is None or not branch.is_active:
                raise SystemExit("Branch does not exist or is inactive.")
            if company_id is not None and branch.company_id != company_id:
                raise SystemExit("Branch does not belong to the selected company.")
            company_id = branch.company_id

        if company_id is not None:
            company = db.get(Company, company_id, execution_options={"scope_bypass": True})
            if company is None or not company.is_active:
                raise SystemExit("Company does not exist or is inactive.")
            if business_group_id is not None and company.business_group_id != business_group_id:
                raise SystemExit("Company does not belong to the selected business group.")
            business_group_id = company.business_group_id

        if business_group_id is None:
            groups = list(db.scalars(select(BusinessGroup).where(BusinessGroup.is_active.is_(True))).all())
            if len(groups) != 1:
                raise SystemExit(
                    "Select --business-group-id explicitly when the Local Hub does not contain exactly one active business group."
                )
            business_group_id = groups[0].id
        else:
            group = db.get(BusinessGroup, business_group_id, execution_options={"scope_bypass": True})
            if group is None or not group.is_active:
                raise SystemExit("Business group does not exist or is inactive.")

    return business_group_id, company_id, branch_id


def register(
    *,
    business_group_id: int | None,
    company_id: int | None,
    branch_id: int | None,
    rotate_secret: bool,
) -> None:
    secret = SettingsCredentialStore(settings).get_secret()
    if not secret:
        raise SystemExit(
            "SYNC_DEVICE_SECRET is required. Generate a strong random secret, store it only in the Local Hub environment file, then rerun."
        )

    cloud_url = settings.cloud_migration_database_url
    if not cloud_url:
        raise SystemExit(
            "CLOUD_MIGRATION_DATABASE_URL is required for trusted device registration. Use the protected direct Supabase migration URL."
        )

    resolved_group, resolved_company, resolved_branch = _resolve_scope(
        business_group_id=business_group_id,
        company_id=company_id,
        branch_id=branch_id,
    )

    with SessionLocal() as db:
        with db.begin():
            identity = DeviceIdentityStore(settings).get_or_create(db)
    device_id = identity.device_id
    credential_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()

    engine = create_engine(cloud_url, pool_pre_ping=True, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            existing = connection.execute(
                select(device_registrations).where(device_registrations.c.device_id == device_id)
            ).mappings().first()
            values = {
                "business_group_id": str(resolved_group),
                "company_id": str(resolved_company) if resolved_company is not None else None,
                "branch_id": str(resolved_branch) if resolved_branch is not None else None,
                "display_name": settings.sync_device_name,
                "credential_hash": credential_hash,
                "status": "active",
                "allowed_purposes": DEFAULT_PURPOSES,
                "revoked_at": None,
            }
            if existing is None:
                connection.execute(
                    insert(device_registrations).values(device_id=device_id, **values)
                )
                action = "registered"
            else:
                if existing["credential_hash"] != credential_hash and not rotate_secret:
                    raise SystemExit(
                        "A cloud registration already exists for this device with a different secret. Rerun with --rotate-secret only after intentionally rotating SYNC_DEVICE_SECRET."
                    )
                connection.execute(
                    update(device_registrations)
                    .where(device_registrations.c.device_id == device_id)
                    .values(**values)
                )
                action = "updated"
    finally:
        engine.dispose()

    print(f"Cloud device {action}: {device_id}")
    print(f"Business group scope: {resolved_group}")
    print(f"Company scope: {resolved_company if resolved_company is not None else 'all companies in business group'}")
    print(f"Branch scope: {resolved_branch if resolved_branch is not None else 'all authorized branches'}")
    print("Allowed purposes:", ", ".join(DEFAULT_PURPOSES))
    print("The raw SYNC_DEVICE_SECRET was not written to the cloud database or printed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register or safely update the Local Hub device in the protected cloud coordination database."
    )
    parser.add_argument("--business-group-id", type=int)
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--branch-id", type=int)
    parser.add_argument(
        "--rotate-secret",
        action="store_true",
        help="Allow replacing an existing registration credential hash with the currently configured SYNC_DEVICE_SECRET.",
    )
    args = parser.parse_args()
    register(
        business_group_id=args.business_group_id,
        company_id=args.company_id,
        branch_id=args.branch_id,
        rotate_secret=args.rotate_secret,
    )


if __name__ == "__main__":
    main()
